# Template AI Apps

Starter repository for eye-tracking app templates — AI course.

## Repository contents

| Folder | What it is |
|---|---|
| `AI Template App/` | **Start here.** Clean starter template with Tobii + PsychoPy |
| `Visual Search/` | Worked example app for reference |
| `x3-120 SDK/` | Tobii X3-120 Python SDK (64-bit) |
| `PsychoPy/` | Local bundled runtime — **not tracked in Git**, install separately |

---

## Student quick-start

### 1. Fork this repo
Click **Fork** (top-right on GitHub) to get your own copy.

### 2. Clone your fork in VS Code
`Ctrl+Shift+P` → **Git: Clone** → paste your fork URL → open the folder.

### 3. Install PsychoPy
Open the VS Code terminal and run:
```
pip install -r "AI Template App/requirements.txt"
```

### 4. Run the template immediately
```
cd "AI Template App"
python ai_template_app.py
```
`DEV_MODE = True` is set by default — **your mouse cursor acts as the simulated gaze point**.  
No eye tracker needed. The app runs on any laptop.

### 5. Build your app with the Copilot agent
Open `AI Template App/ai_template_app.py` and use the VS Code Copilot agent to modify it.  
Key extension points are marked with `# STUDENT EXERCISE` comments.  
Keep `DEV_MODE = True` while you develop so you can test on your laptop with the mouse.

### 6. Hand in for real-hardware testing
When your app is ready:
1. Set `DEV_MODE = False` in `ai_template_app.py`
2. Commit and push to your fork
3. Tell the teacher your fork URL

The teacher will clone your fork, plug in the Tobii X3-120, and run your app against the real eye tracker.

---

## DEV_MODE explained

| `DEV_MODE` | Tobii needed? | Gaze source | Use when |
|---|---|---|---|
| `True` | No | Mouse cursor | Building & testing on your laptop |
| `False` | Yes | Real Tobii X3-120 | Final test on teacher's machine |

**Only change this flag — everything else stays the same between dev and production.**

---

## Teacher: testing a student submission
```bash
git clone https://github.com/<student-group>/Template-AI-Apps  group-X
cd "group-X/AI Template App"
# confirm DEV_MODE = False is set, then:
python ai_template_app.py
```

---

## Note on PsychoPy
`PsychoPy/` is excluded from Git because it is ~1.2 GB.  
Install it on each machine via `pip install psychopy` or download the standalone from https://www.psychopy.org/download.html
