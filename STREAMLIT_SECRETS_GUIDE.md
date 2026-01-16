# 🔐 How to Add Secrets in Streamlit Cloud

## Step 1: Deploy Your App First

Deploy your app to Streamlit Cloud (your app must be deployed before adding secrets).

Your app will be at: https://autodocx-YOUR_USERNAME.streamlit.app

---

## Step 2: Open App Settings

1. Go to your deployed app: https://autodocx-YOUR_USERNAME.streamlit.app
2. Look for the ⚙️ Settings button (top right corner)
3. Click on it

![Settings Location]
- Top right corner of your Streamlit app
- Button looks like a gear icon ⚙️

---

## Step 3: Navigate to Secrets

In the settings dropdown menu:
1. Click "Secrets"
2. You'll see a text area that says "Secrets (TOML format)"

---

## Step 4: Add Your Secrets

Paste this in the secrets text area (replace with your actual key):

```toml
OPENAI_API_KEY="your-key-here"
```

### Format Notes:
- Use TOML format (key = "value")
- Keep quotes around the value
- `OPENAI_API_KEY` must match what your code expects

---

## Step 5: Save and Wait

1. Click "Save" button
2. ⏳ Wait 1-2 minutes for changes to propagate
3. Streamlit will automatically reload your app with the new secrets

---

## Step 6: Verify It Works

After 1-2 minutes:
1. Refresh your app (press F5 or Ctrl+R)
2. Try uploading a repository
3. Try generating documentation
4. Your app should now have access to the OpenAI API

---

## If It Doesn't Work

### ❌ Still getting "API key not set" error

Solution:
1. Check that secret key is pasted correctly (no extra spaces)
2. Wait another 1-2 minutes
3. Click ⚙️ Settings → Reboot to restart the app
4. Verify the key format in secrets matches exactly:
   ```toml
   OPENAI_API_KEY="your-key-here"
   ```

### ❌ Secrets button not visible

Solution:
1. Make sure app is fully deployed
2. Try refreshing the page
3. Clear browser cache (Ctrl+Shift+Delete)
4. Try in an incognito window

---

## What Happens Behind the Scenes

Your code (app/config.py) does this:
```python
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
```

When you add a secret in Streamlit Cloud:
- It automatically sets it as an environment variable
- Your code automatically reads it
- No code changes needed! ✅

---

## Your Complete Secret

Copy and paste this entire line in the Secrets text area:

```toml
OPENAI_API_KEY="your-key-here"
```

Then click Save and wait 1-2 minutes.

That's it! 🚀
