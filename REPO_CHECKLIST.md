# GitHub Repo Checklist

Use this checklist before pushing to ensure your repo is ready for others to clone and run.

## ✅ Essential Files

- [x] **README.md** - Comprehensive overview with quickstart
- [x] **SETUP.md** - Detailed setup instructions
- [x] **requirements.txt** - All Python dependencies
- [x] **.gitignore** - Excludes large files, secrets, etc.
- [x] **.env.example** - Template for environment variables
- [x] **LICENSE** - MIT or your chosen license
- [x] **paligemma_stockout_model/README.md** - How to get the model
- [x] **media/videos/README.md** - Video instructions

## ✅ Code Structure

- [x] **manage.py** - Django entry point
- [x] **stockout_demo/** - Django project settings
- [x] **detector/** - Main app with views, models, templates
- [x] **static/** - CSS, JS, images (blueprint)
- [x] **media/videos/** - Directory for demo videos (empty in repo)

## ✅ Documentation Quality

- [x] Clear problem statement (stock-outs)
- [x] Vusion use case highlighted (on-shelf cameras)
- [x] Installation steps (3 options for model)
- [x] Troubleshooting section
- [x] API documentation
- [x] Architecture diagram
- [x] Screenshots/GIFs (optional but recommended)

## ⚠️ Before Pushing

### 1. Clean Up Temporary Files
```bash
# Remove cache
find . -type d -name "__pycache__" -exec rm -rf {} +
find . -name "*.pyc" -delete

# Remove OS files
find . -name ".DS_Store" -delete

# Remove logs
rm -f *.log
```

### 2. Verify .gitignore
```bash
# Check what will be committed
git status
git ls-files | grep -E "(\.sqlite3|\.mp4|\.safetensors|\.env)"
# Should return nothing (these should be ignored)
```

### 3. Test Fresh Clone Simulation
```bash
# In a separate directory
git clone /path/to/your/repo test-clone
cd test-clone

# Try to run (will fail at model loading - that's expected)
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

### 4. Sensitive Data Check
```bash
# Search for API keys or secrets
grep -r "API_KEY" . --include="*.py"
grep -r "SECRET_KEY" . --include="*.py"
# Verify all are loaded from environment variables
```

### 5. File Sizes
```bash
# Check repo size (should be < 100MB)
du -sh .

# Check for large files
find . -type f -size +10M
# Should only find videos (which are gitignored)
```

## ✅ Repository Settings (on GitHub)

Once pushed, configure:

- [ ] **Description:** "On-device stock-out detection for Vusion shelf cameras using PaliGemma"
- [ ] **Topics:** `machine-learning`, `edge-ai`, `retail`, `computer-vision`, `paligemma`, `vusion`
- [ ] **README:** Visible on repo homepage
- [ ] **License:** MIT (or your choice)
- [ ] **Issues:** Enabled for bug reports
- [ ] **Releases:** Tag v1.0.0 when stable

## ✅ Optional Enhancements

- [ ] **Screenshots** - Add demo UI screenshots to README
- [ ] **Demo GIF** - Record 10-second demo using Kap or similar
- [ ] **Architecture Diagram** - Create visual diagram (draw.io, Excalidraw)
- [ ] **GitHub Actions** - Add CI for linting/tests
- [ ] **Pre-commit Hooks** - Auto-format code
- [ ] **CONTRIBUTING.md** - Guidelines for contributors
- [ ] **CHANGELOG.md** - Version history

## ✅ Model Distribution

Since the model is too large for git, choose one:

### Option A: HuggingFace Model Hub
```bash
huggingface-cli upload namanbansalcodes/paligemma-stockout ./paligemma_stockout_model
```
Update README with download command.

### Option B: Google Drive / Dropbox
Upload model, get shareable link, add to README.

### Option C: GitHub Release
Use GitHub Releases to attach the model files (up to 2GB).

### Option D: Document in README
Provide SCP instructions from training server (current approach).

## ⚙️ Quick Commands

```bash
# Stage all changes
git add .

# Check what will be committed
git status
git diff --cached

# Commit
git commit -m "feat: add comprehensive setup documentation"

# Push to GitHub
git push origin main  # or master, or your branch
```

## 📋 Final Verification

After pushing, verify on GitHub:

1. Clone the repo fresh in a new location
2. Follow SETUP.md exactly
3. Verify all links work
4. Check code blocks render correctly
5. Test that someone unfamiliar can run it

## 🎉 Ready to Share!

Your repo is ready when:
- ✅ README clearly explains the problem (stock-outs) and solution (Vusion cameras)
- ✅ Setup instructions work on a fresh machine
- ✅ No secrets or large files committed
- ✅ Documentation is clear and complete
- ✅ Code runs without errors (after model is obtained)

---

**Hackathon judges will see:**
1. README (30 seconds)
2. Code quality (2 minutes)
3. Demo (if live)

Make sure your README hooks them in the first 30 seconds!
