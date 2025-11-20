# Gmail SMTP Setup Guide

## 📧 How to Get Gmail App Password

To send emails via Gmail SMTP, you need to create an **App Password** (not your regular Gmail password).

### Step 1: Enable 2-Factor Authentication

1. Go to your Google Account: https://myaccount.google.com/
2. Click on **Security** in the left sidebar
3. Under "How you sign in to Google", click **2-Step Verification**
4. Follow the prompts to enable 2FA if not already enabled

### Step 2: Generate App Password

1. Go to: https://myaccount.google.com/apppasswords
   - OR: Google Account → Security → 2-Step Verification → App passwords
2. You may need to sign in again
3. Under "Select app", choose **Mail**
4. Under "Select device", choose **Other (Custom name)**
5. Enter a name like "DevSyncSalesAI"
6. Click **Generate**
7. Google will show you a 16-character password (like: `abcd efgh ijkl mnop`)
8. **Copy this password** - you won't be able to see it again!

### Step 3: Update .env File

Open your `.env` file and update the SMTP_PASSWORD:

```env
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=anshum25506@gmail.com
SMTP_PASSWORD=abcdefghijklmnop
```

**Note**: Remove the spaces from the app password when pasting it.

### Step 4: Test Email Sending

Run the test script:

```bash
python send_test_email.py
```

You should see:
```
✅ Email sent successfully!
Message ID: ...
🎉 Check inbox: anshum25506@gmail.com
```

## 🔒 Security Notes

- **Never share your App Password**
- App Passwords bypass 2FA, so keep them secure
- You can revoke App Passwords anytime from your Google Account
- Each app should have its own App Password

## ⚠️ Troubleshooting

### "Username and Password not accepted"
- Make sure 2FA is enabled on your Google Account
- Verify you're using an App Password, not your regular password
- Check that SMTP_USER matches the Gmail account that generated the App Password

### "Less secure app access"
- This is no longer needed if you use App Passwords
- App Passwords are the secure way to access Gmail via SMTP

### Still not working?
- Check if Gmail is blocking the sign-in attempt
- Go to: https://myaccount.google.com/notifications
- Look for security alerts and allow the access

## 📝 Alternative: Use a Different Email

If you don't want to use Gmail, you can:

1. **Use SendGrid** (requires sender verification)
2. **Use Mailgun** (requires domain setup)
3. **Use another SMTP provider** (update SMTP settings accordingly)

---

**Once configured, emails will be sent from**: `mauryadoshi1@gmail.com`
**Test email will be sent to**: `anshum25506@gmail.com`
