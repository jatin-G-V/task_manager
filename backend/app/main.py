import json
import logging
import os

import httpx
from fastapi import FastAPI, Depends, HTTPException, Request
from pydantic import BaseModel

from app.db.supabase_client import supabase
from app.auth import get_current_user
from app.services.task_parser import parse_task_text
from app.routers.tasks import router as tasks_router
from app.routers.feedback import router as feedback_router
from app.routers.settings import router as settings_router
from app.services import recommend_reply, reply_writer
from app.services.agent import run_agent
from app.services.agent_tools import clear_user_pending


app = FastAPI()

logger = logging.getLogger(__name__)
GEMINI_FILES_URL = "https://generativelanguage.googleapis.com/upload/v1beta/files"
GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta"
TRANSCRIPTION_MODEL = "gemini-3.5-transcribe"
MAX_AUDIO_BYTES = 12 * 1024 * 1024

app.include_router(tasks_router)
app.include_router(feedback_router)
app.include_router(settings_router)

# lets the model say "another=true" for "something else"
recommend_reply.install()


@app.post("/transcribe")
async def transcribe_audio(
    request: Request,
    user_id: str = Depends(get_current_user),
):
    # Audio stays in memory on our backend. The API key is only read server-side.
    api_key = os.getenv("AGENT_API_KEY")
    if not api_key:
        raise HTTPException(status_code=503, detail="Transcription is not configured.")

    allowed_mime_types = {
        "audio/mp4",
        "audio/m4a",
        "audio/aac",
        "audio/webm",
        "audio/mpeg",
        "audio/ogg",
        "audio/wav",
    }
    request_mime_type = request.headers.get("content-type", "").split(";", 1)[0].lower()
    declared_mime_type = request.headers.get("x-audio-mime-type", "").split(";", 1)[0].lower()
    # Native fetch implementations may serialize a File body as
    # application/octet-stream despite an explicit Content-Type. The client
    # also sends its detected recording type separately, which we validate.
    mime_type = (
        request_mime_type
        if request_mime_type in allowed_mime_types
        else declared_mime_type
    )
    if mime_type not in allowed_mime_types:
        logger.info(
            "Rejected transcription MIME types: content-type=%r declared=%r",
            request_mime_type,
            declared_mime_type,
        )
        raise HTTPException(status_code=415, detail="Unsupported audio format.")

    content_length = request.headers.get("content-length")
    if content_length and content_length.isdigit() and int(content_length) > MAX_AUDIO_BYTES:
        raise HTTPException(status_code=413, detail="Recording is too large. Keep it under 60 seconds.")

    audio = bytearray()
    async for chunk in request.stream():
        audio.extend(chunk)
        if len(audio) > MAX_AUDIO_BYTES:
            raise HTTPException(status_code=413, detail="Recording is too large. Keep it under 60 seconds.")

    logger.warning("Transcription received %d bytes (%s)", len(audio), mime_type)
    if not audio:
        logger.warning("Transcription rejected: request audio body was empty")
        raise HTTPException(status_code=422, detail="The recording upload was empty. Please try again.")

    remote_file_name = None
    headers = {"x-goog-api-key": api_key}
    timeout = httpx.Timeout(90.0, connect=15.0)

    async with httpx.AsyncClient(timeout=timeout) as client:
        try:
            start_response = await client.post(
                GEMINI_FILES_URL,
                headers={
                    **headers,
                    "X-Goog-Upload-Protocol": "resumable",
                    "X-Goog-Upload-Command": "start",
                    "X-Goog-Upload-Header-Content-Length": str(len(audio)),
                    "X-Goog-Upload-Header-Content-Type": mime_type,
                    "Content-Type": "application/json",
                },
                json={"file": {"display_name": "task-voice-input"}},
            )
            if start_response.status_code == 429:
                raise HTTPException(status_code=429, detail="Transcription is busy. Please try again shortly.")
            start_response.raise_for_status()

            upload_url = start_response.headers.get("x-goog-upload-url")
            if not upload_url:
                raise HTTPException(status_code=502, detail="Could not start audio transcription.")

            upload_response = await client.post(
                upload_url,
                headers={
                    "X-Goog-Upload-Offset": "0",
                    "X-Goog-Upload-Command": "upload, finalize",
                    "Content-Length": str(len(audio)),
                },
                content=bytes(audio),
            )
            if upload_response.status_code == 429:
                raise HTTPException(status_code=429, detail="Transcription is busy. Please try again shortly.")
            upload_response.raise_for_status()

            uploaded_file = upload_response.json().get("file", {})
            remote_file_name = uploaded_file.get("name")
            file_uri = uploaded_file.get("uri")
            if not remote_file_name or not file_uri:
                raise HTTPException(status_code=502, detail="Could not process the recording.")

            interaction_response = await client.post(
                f"{GEMINI_API_URL}/interactions",
                headers={**headers, "Content-Type": "application/json"},
                json={
                    "model": TRANSCRIPTION_MODEL,
                    "input": [{"type": "audio", "uri": file_uri, "mime_type": mime_type}],
                    "generation_config": {
                        "transcription_config": {
                            "language_codes": ["en-US"],
                            "mode": "smart",
                        }
                    },
                },
            )
            if interaction_response.status_code == 429:
                raise HTTPException(status_code=429, detail="Transcription is busy. Please try again shortly.")
            interaction_response.raise_for_status()

            interaction = interaction_response.json()
            output_text = interaction.get("output_text")
            if isinstance(output_text, str) and output_text.strip():
                transcript = output_text.strip()
            else:
                # The current Interactions REST response returns generated
                # content in model_output steps. output_text is an SDK
                # convenience property and may not be present in raw REST JSON.
                text_parts = []
                for step in interaction.get("steps", []) or []:
                    if not isinstance(step, dict) or step.get("type") != "model_output":
                        continue
                    for content in step.get("content", []) or []:
                        if (
                            isinstance(content, dict)
                            and content.get("type") == "text"
                            and isinstance(content.get("text"), str)
                        ):
                            text_parts.append(content["text"])

                # Support the previous Interactions response shape too.
                if not text_parts:
                    for output in interaction.get("outputs", []) or []:
                        if isinstance(output, dict) and isinstance(output.get("text"), str):
                            text_parts.append(output["text"])

                transcript = " ".join(part.strip() for part in text_parts if part.strip())
            if not transcript:
                logger.warning(
                    "Transcription returned no text for %d-byte audio; response keys=%s",
                    len(audio),
                    sorted(interaction.keys()),
                )
                raise HTTPException(status_code=422, detail="I couldn't hear any words. Please try recording again.")

            return {"text": transcript}

        except HTTPException:
            raise
        except httpx.HTTPStatusError as exc:
            logger.warning("Gemini transcription request failed with status %s", exc.response.status_code)
            raise HTTPException(status_code=502, detail="Transcription failed. Please try again.") from exc
        except (httpx.TimeoutException, httpx.RequestError) as exc:
            logger.warning("Gemini transcription request failed: %s", type(exc).__name__)
            raise HTTPException(status_code=503, detail="Transcription is temporarily unavailable.") from exc
        except (ValueError, json.JSONDecodeError) as exc:
            logger.warning("Gemini returned an invalid transcription response")
            raise HTTPException(status_code=502, detail="Could not read the transcription response.") from exc
        finally:
            # Gemini temporarily holds uploaded files; remove them after use.
            if remote_file_name:
                try:
                    delete_response = await client.delete(
                        f"{GEMINI_API_URL}/{remote_file_name}",
                        headers=headers,
                    )
                    delete_response.raise_for_status()
                except httpx.HTTPError:
                    logger.warning("Could not delete temporary Gemini audio file")


@app.get("/health")
def health_check():
    return {"status": "ok"}


class ParseRequest(BaseModel):
    text: str


@app.post("/parse-task")
def parse_task(
    req: ParseRequest,
    user_id: str = Depends(get_current_user)
):
    if not req.text.strip():
        raise HTTPException(
            status_code=400,
            detail="text is required"
        )

    try:
        return parse_task_text(req.text)

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )


class ChatRequest(BaseModel):
    messages: list[dict]


@app.post("/agent/chat")
def agent_chat(req: ChatRequest, user_id: str = Depends(get_current_user)):
    has_assistant_history = any(
        isinstance(message, dict) and message.get("role") == "assistant"
        for message in req.messages
    )
    logger.info(
        "CHAT start messages=%d fresh_chat=%s",
        len(req.messages),
        not has_assistant_history,
    )
    if not has_assistant_history:
        clear_user_pending(user_id)
    reply, tasks_changed = run_agent(user_id, req.messages)

    # Optional per-user style. Returns the reply unchanged unless the user saved
    # a style note and the reply is a safe success/info message.
    reply = reply_writer.polish(user_id, reply)

    logger.info("CHAT done tasks_changed=%s reply_chars=%d", tasks_changed, len(reply))
    return {"reply": reply, "tasks_changed": tasks_changed}