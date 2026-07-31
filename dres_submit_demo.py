"""
DRES Client Submission Utility
==============================
Module and CLI tool to submit retrieval results to DRES (Distributed Retrieval Evaluation Server).
"""

import os
import argparse
import requests
from typing import List, Optional, Dict, Any

# Environment variables or manual default fallback settings
DRES_BASE_URL = os.getenv("DRES_BASE_URL", "http://localhost:5000")
SESSION_ID: Optional[str] = os.getenv("DRES_SESSION_ID", None)
USERNAME: Optional[str] = os.getenv("DRES_USERNAME", None)
PASSWORD: Optional[str] = os.getenv("DRES_PASSWORD", None)
DEFAULT_FPS: float = 25.0

ResultItem = Dict[str, Any]


def get_session_id(base_url: str = DRES_BASE_URL, session_id: Optional[str] = SESSION_ID, username: Optional[str] = USERNAME, password: Optional[str] = PASSWORD) -> str:
    """Get active session ID from direct string or via API login"""
    if session_id:
        print("[info] Using provided SESSION_ID.")
        return session_id

    if not username or not password:
        raise RuntimeError(
            "No SESSION_ID provided and USERNAME/PASSWORD not set. "
            "Please provide a valid session ID or login credentials."
        )

    login_url = f"{base_url}/api/v2/login"
    payload = {"username": username, "password": password}
    resp = requests.post(login_url, json=payload, timeout=10)
    if not resp.ok:
        try:
            err = resp.json()
        except Exception:
            err = {"error": resp.text}
        raise RuntimeError(f"Login failed: HTTP {resp.status_code} - {err}")

    data = resp.json()
    sid = data.get("sessionId") or data.get("sessionID") or data.get("session_id")
    if not sid:
        raise RuntimeError(f"Login response missing sessionId: {data}")
    print("[info] Auto-login success. sessionId =", sid)
    return sid


def get_active_evaluation_id(session_id: str, base_url: str = DRES_BASE_URL) -> str:
    """Fetch active evaluation ID from DRES server"""
    url = f"{base_url}/api/v2/client/evaluation/list"
    resp = requests.get(url, params={"session": session_id}, timeout=10)
    if not resp.ok:
        raise RuntimeError(f"Get evaluation list failed: HTTP {resp.status_code} - {resp.text}")

    evaluations = resp.json()
    active = next((e for e in evaluations if str(e.get("status")).upper() == "ACTIVE"), None)
    if not active:
        raise RuntimeError("No active evaluation task found on DRES server.")
    return str(active.get("id"))


def ms_from_frame_index(frame_value: Any, fps: float = DEFAULT_FPS) -> int:
    """Convert video frame index to milliseconds based on FPS"""
    frame_index = int(frame_value)
    return int((frame_index / fps) * 1000)


def submit_result(
    result: ResultItem,
    session_id: str,
    evaluation_id: str,
    base_url: str = DRES_BASE_URL,
    question: Optional[str] = None,
    fps: float = DEFAULT_FPS,
) -> Dict[str, Any]:
    """Submit a single result item (item timestamp or VQA answer) to DRES"""
    video_id = str(result["videoId"])
    timestamp = result["timestamp"]

    if question:
        ms = ms_from_frame_index(timestamp, fps=fps)
        text = f"QA-{question}-{video_id}-{ms}"
        body = {"answerSets": [{"answers": [{"text": text}]}]}
    else:
        ms = ms_from_frame_index(timestamp, fps=fps)
        body = {
            "answerSets": [
                {
                    "answers": [
                        {"mediaItemName": video_id, "start": ms, "end": ms}
                    ]
                }
            ]
        }

    url = f"{base_url}/api/v2/submit/{evaluation_id}"
    resp = requests.post(url, params={"session": session_id}, json=body, timeout=15)
    if not resp.ok:
        try:
            raise RuntimeError(resp.json().get("description", resp.text))
        except Exception:
            raise RuntimeError(f"DRES submission failed: HTTP {resp.status_code} - {resp.text}")

    data = resp.json()
    print("✅ DRES submission response:", data)
    return data


def full_submission_flow(result: ResultItem, base_url: str = DRES_BASE_URL, question: Optional[str] = None, fps: float = DEFAULT_FPS) -> Dict[str, Any]:
    session_id = get_session_id(base_url=base_url)
    evaluation_id = get_active_evaluation_id(session_id, base_url=base_url)
    return submit_result(result, session_id, evaluation_id, base_url=base_url, question=question, fps=fps)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Submit search result to DRES server.")
    parser.add_argument("--video-id", type=str, default="K01_V001", help="Video item identifier.")
    parser.add_argument("--frame-id", type=int, default=123, help="Keyframe frame index.")
    parser.add_argument("--dres-url", type=str, default=DRES_BASE_URL, help="DRES Base URL.")
    parser.add_argument("--fps", type=float, default=DEFAULT_FPS, help="Video FPS rate.")

    args = parser.parse_args()

    sample_result = {"videoId": args.video_id, "timestamp": args.frame_id}
    print(f"Submitting test result: {sample_result} to DRES at {args.dres_url}...")
    try:
        resp = full_submission_flow(sample_result, base_url=args.dres_url, fps=args.fps)
        print("Submit OK:", resp)
    except Exception as e:
        print("Submit error:", e)
