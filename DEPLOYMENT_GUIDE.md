# 🚀 Complete Deployment Guide for Render

## Prerequisites Checklist
- ✅ Code pushed to GitHub
- ✅ Neon PostgreSQL database created
- ✅ API key ready (OpenAI/Groq/Together)

---

## Step 1: Create New Web Service on Render

1. Go to [Render Dashboard](https://dashboard.render.com)
2. Click **"New +"** → **"Web Service"**
3. Connect your GitHub account if not already connected
4. Select your repository: `StratMaker-v2.0` (or whatever you named it)
5. Click **"Connect"**

---

## Step 2: Configure Service Settings

Fill in these fields:

### Basic Settings:
- **Name**: `stratyx` (or any name you prefer)
  - ⚠️ **This name determines your URL**: `https://your-service-name.onrender.com`
  - Choose a name you like - it will be part of your public URL
  - You can change it later in Settings → Name
- **Region**: Choose closest to you (e.g., `Oregon (US West)`)
- **Branch**: `master` (or `main` if that's your default branch)
- **Root Directory**: Leave empty (or `.` if needed)

### Build & Deploy:
- **Environment**: Select **`Python 3`**
- **Build Command**: 
  ```
  pip install -r requirements.txt
  ```
- **Start Command**: 
  ```
  gunicorn app:app
  ```

### ⚠️ CRITICAL: Python Version
- **Render will automatically detect `runtime.txt` file** (which specifies Python 3.11.9)
- If you see a **"Python Version"** option anywhere, set it to **`3.11.9`** or **`3.11`**
- If you DON'T see this option, that's OK - Render should auto-detect from `runtime.txt`
- **After first deploy, check logs to confirm Python 3.11.9 is being used**

---

## Step 3: Add Environment Variables

Click **"Add Environment Variable"** and add these one by one:

### Database Variables:
```
DATABASE_URL = postgresql+psycopg2://neondb_owner:YOUR_PASSWORD@ep-soft-wind-ahkjbatu-pooler.c-3.us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require
```

```
DATABASE_URL_PG = postgresql://neondb_owner:YOUR_PASSWORD@ep-soft-wind-ahkjbatu-pooler.c-3.us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require
```

**⚠️ Replace `YOUR_PASSWORD` with your actual Neon database password!**

### Application Variables:
```
AUTO_CREATE_DB = false
```

```
SECRET_KEY = [Generate a random string - use any long random text]
```
Example: `your-super-secret-key-change-this-to-random-string-12345`

### AI Model Variables:

**Option A: Using OpenAI**
```
MODEL = gpt-4o-mini
```
```
API_KEY = sk-your-openai-api-key-here
```
```
API_BASE_URL = [Leave this EMPTY or don't add it]
```

**Option B: Using Groq (FREE)**
```
MODEL = llama-3.1-70b-versatile
```
```
API_KEY = gsk_your-groq-api-key-here
```
```
API_BASE_URL = https://api.groq.com/openai/v1
```

**Option C: Using Together AI**
```
MODEL = meta-llama/Llama-3-70b-chat-hf
```
```
API_KEY = your-together-api-key-here
```
```
API_BASE_URL = https://api.together.xyz/v1
```

### Optional (if using Google Login):
```
GOOGLE_CLIENT_ID = your-google-client-id-here
```

---

## Step 4: Create and Deploy

1. Scroll to the bottom
2. Click **"Create Web Service"**
3. Render will start building your app
4. Watch the build logs - you should see:
   - ✅ Python 3.11.9 being used
   - ✅ Installing dependencies from requirements.txt
   - ✅ Starting gunicorn

---

## Step 5: Verify Deployment

### Check Build Logs:
- Look for: `Python 3.11.9` (NOT 3.13!)
- Look for: `Successfully installed` messages
- Look for: `Starting gunicorn`

### If Build Fails:
- Check the error message in logs
- Common issues:
  - **Python 3.13 error**: Go back to Settings → Set Python Version to 3.11.9
  - **Database connection error**: Check DATABASE_URL and DATABASE_URL_PG are correct
  - **Missing env var**: Make sure all required variables are set

### If Build Succeeds:
- Your app will be live at: `https://your-app-name.onrender.com`
- The first deploy may take 2-3 minutes
- Free tier services "sleep" after 15 minutes of inactivity (wakes up on first request)

---

## Step 6: Test Your App

1. Visit your Render URL
2. Test signup/login
3. Test the main functionality
4. Check database connections work

---

## Troubleshooting

### Service keeps crashing:
- Check **Logs** tab for error messages
- Verify all environment variables are set correctly
- Ensure Python version is 3.11.9

### Database connection errors:
- Verify DATABASE_URL format is correct
- Check Neon database is running
- Ensure password in URL matches Neon password

### Import errors:
- Check requirements.txt is correct
- Verify Python version is 3.11.9 (not 3.13)
- Check build logs for installation errors

---

## Quick Reference: All Environment Variables

Copy-paste this checklist:

- [ ] `DATABASE_URL` (with +psycopg2)
- [ ] `DATABASE_URL_PG` (without +psycopg2)
- [ ] `AUTO_CREATE_DB` = `false`
- [ ] `SECRET_KEY` = (random string)
- [ ] `MODEL` = (your model name)
- [ ] `API_KEY` = (your API key)
- [ ] `API_BASE_URL` = (your provider URL or empty)
- [ ] `GOOGLE_CLIENT_ID` = (optional)

---

## Need Help?

If deployment fails, share:
1. The error message from Render logs
2. Which step you're on
3. Screenshot of your environment variables (hide passwords!)

Good luck! 🎉

