# How to Add 100 Business Leads to Render

## 🎯 Quick Solution: Use Admin API

Your app now has an admin endpoint to seed the database!

### **Step 1: Seed Database**

```bash
curl -X POST https://your-app.onrender.com/api/v1/admin/seed-leads
```

**Response:**
```json
{
  "message": "Successfully seeded database",
  "leads_added": 100,
  "total_leads": 100,
  "action": "completed"
}
```

### **Step 2: Verify Leads Added**

```bash
curl https://your-app.onrender.com/api/v1/admin/stats
```

**Response:**
```json
{
  "leads": {
    "total": 100,
    "verified": 100,
    "opted_out": 0
  },
  "campaigns": {
    "total": 1
  },
  "emails": {
    "total_sent": 0
  }
}
```

### **Step 3: Trigger Email Campaign**

```bash
curl -X POST https://your-app.onrender.com/api/v1/campaigns/trigger/email
```

**Expected Result:**
```json
{
  "success": true,
  "message": "Email campaign executed successfully",
  "report": {
    "campaign_id": 2,
    "total_attempted": 100,
    "total_success": 100,
    "total_failed": 0
  }
}
```

## 📊 Check Results

### View All Leads

```bash
curl https://your-app.onrender.com/api/v1/leads
```

### View Campaign Stats

```bash
curl https://your-app.onrender.com/api/v1/stats
```

## 🔄 Reset Database (if needed)

```bash
# Clear all leads
curl -X DELETE https://your-app.onrender.com/api/v1/admin/clear-leads

# Seed again
curl -X POST https://your-app.onrender.com/api/v1/admin/seed-leads
```

## 🚀 Complete Workflow

```bash
# 1. Seed database with 100 leads
curl -X POST https://your-app.onrender.com/api/v1/admin/seed-leads

# 2. Verify leads added
curl https://your-app.onrender.com/api/v1/admin/stats

# 3. Send emails immediately
curl -X POST https://your-app.onrender.com/api/v1/campaigns/trigger/email

# 4. Check results
curl https://your-app.onrender.com/api/v1/stats
```

## ✅ What You'll Get

- **99 placeholder business emails** (contact1@business1.com, contact2@business2.com, etc.)
- **1 real demo email** (anshum25506@gmail.com)
- All marked as verified and ready to send
- Distributed across Indian cities
- Various business categories

## 📧 Email Distribution

The 100 emails will be sent to:
- `contact1@business1.com` through `contact99@business99.com` (99 emails)
- `anshum25506@gmail.com` (1 email)

## ⚠️ Important Notes

1. **Placeholder Emails**: The 99 business emails are placeholders. They won't actually receive emails (invalid addresses).
2. **Real Email**: Only `anshum25506@gmail.com` will receive a real email.
3. **Replace with Real Data**: For production, replace placeholder emails with real business contacts.

## 🔧 Alternative: Add Real Business Data

If you have real business data, use the Python script:

```bash
python add_leads_to_render.py https://your-app.onrender.com
```

Or add leads one by one via API:

```bash
curl -X POST https://your-app.onrender.com/api/v1/leads \
  -H "Content-Type: application/json" \
  -d '{
    "source": "google_maps",
    "business_name": "Real Business Name",
    "primary_email": "real@business.com",
    "city": "Mumbai",
    "category": "IT Services",
    "email_verified": true
  }'
```

---

**Now push the changes and redeploy!**

```bash
git add .
git commit -m "Added admin API for seeding leads"
git push origin main
```

Then run:
```bash
curl -X POST https://your-app.onrender.com/api/v1/admin/seed-leads
```
