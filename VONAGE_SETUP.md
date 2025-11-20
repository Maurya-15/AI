# Vonage Setup Guide

## 📞 Getting Your Vonage Credentials

You've provided the API Key: `taMrE0mBmp8WF6cT`

Now you need to get:
1. **API Secret**
2. **Phone Number**

### Step 1: Get API Secret

1. Go to: https://dashboard.nexmo.com/
2. Log in with your Vonage account
3. On the dashboard, you'll see:
   - **API Key**: `taMrE0mBmp8WF6cT` (you already have this)
   - **API Secret**: Click "Show" to reveal it
4. Copy the API Secret

### Step 2: Get/Buy a Phone Number

1. In the Vonage Dashboard, go to **Numbers** → **Your Numbers**
2. If you already have a number, copy it
3. If you don't have a number:
   - Click **Buy Numbers**
   - Select your country (India)
   - Choose "Voice" capability
   - Purchase a number

### Step 3: Update .env File

Open your `.env` file and update:

```env
VONAGE_API_KEY=taMrE0mBmp8WF6cT
VONAGE_API_SECRET=your_actual_api_secret_here
VONAGE_PHONE_NUMBER=your_vonage_number_here
```

**Example:**
```env
VONAGE_API_KEY=taMrE0mBmp8WF6cT
VONAGE_API_SECRET=abcdef1234567890
VONAGE_PHONE_NUMBER=919876543210
```

**Note**: Vonage phone numbers should be in international format without the `+` sign.

### Step 4: Test the Call

Run:
```bash
python send_test_call.py
```

You should see:
```
Using Provider: VONAGE
✅ Call initiated successfully!
```

## 🔧 Troubleshooting

### "API Secret not configured"
- Make sure you've copied the API Secret from the dashboard
- Check that there are no extra spaces in the .env file

### "Phone number not configured"
- Verify you have a phone number in your Vonage account
- Make sure the number is in international format (e.g., `919876543210`)

### "Insufficient balance"
- Check your Vonage account balance
- Add credits if needed

## 💰 Vonage Pricing

- **Voice calls to India**: ~$0.01-0.02 per minute
- **Phone number rental**: ~$1-2 per month

## 📝 Next Steps

Once configured:
1. Test with: `python send_test_call.py`
2. The call will be made to: `+917698895249`
3. You'll hear an AI voice message
4. The system will record the response

---

**Need help?** Check the Vonage documentation: https://developer.vonage.com/voice/voice-api/overview
