# Frontend Web UI

HTML5 + CSS3 + Vanilla JS interface for video retrieval. Connects to backend via WebSocket for real-time results.

Supported browsers: Chrome, Edge, Brave.

---

## Access

```
http://localhost:8000/frontend/
```

Backend must be running on port 8000 (`python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000`).

---

## Module Map

| File | Description |
| :--- | :--- |
| `index.html` | Main search UI and submission tray |
| `login.html` | DRES session config (URL, sessionId, evaluationID) |
| `scripts/config.js` | API_BASE, WS_URL constants |
| `scripts/websocket.js` | WebSocket client, search dispatch, result handling |
| `scripts/update_result.js` | Render result grid, neighbor scrubbing panel |
| `scripts/submit_dres.js` | KIS/QA/TRAKE submission to DRES API |
| `scripts/show_video.js` | Inline video player with timestamp seek |
| `scripts/show_videoframe.js` | Keyframe neighbor strip viewer |
| `scripts/export.js` | Submission tray management, CSV export, zip pack |
| `scripts/left_panel.js` | Query input panel, tab switching, history |
| `scripts/preview.js` | Keyframe preview hover panel |
| `scripts/pagination.js` | Result page controls |
| `scripts/filter_info.js` | OCR/ASR text filter overlay |
| `scripts/query_history.js` | Session query history display |
| `scripts/start_ui.js` | UI initialization on page load |
| `scripts/shortcuts.js` | Global keyboard shortcut bindings |

---

## Keyboard Shortcuts

| Shortcut | Action |
| :--- | :--- |
| `Enter` | Submit search query |
| `Middle-click` / `[+]` | Add keyframe to submission tray |
| `Alt+A` | Toggle submission tray |
| `Alt+R` | Rocchio relevance feedback (rerank from selected frames) |
| `Alt+S` | Save current query result to session |
| `Ctrl+S` / `Alt+P` | Open submission pack panel, create `submission.zip` |
| `Ctrl+Q` | Clear search input |
| `Ctrl+I` | Switch to OCR search tab |
| `Ctrl+K` | Switch to ASR search tab |
| `Alt+C` / `Alt+X` | Clear submission tray |
| `Esc` | Close video player or modal |

---

## Task Types

- **KIS (Known-Item Search):** Select 1-3 keyframes matching the described moment. MRR scoring — fewer frames = higher potential score.
- **Q&A:** Select 1 keyframe as visual evidence + type a short text answer.
- **TRAKE:** Select an ordered sequence of keyframes from the same video across multiple temporal stages.
