from pyrogram import Client, filters
from pymongo import MongoClient
import os
from dotenv import load_dotenv

# ✅ Load Environment Variables
load_dotenv()
API_ID = os.getenv("API_ID")
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")
MONGO_URI = os.getenv("MONGO_URI")
ADMIN_ID = int(os.getenv("ADMIN_ID"))
ADMIN_UPI_ID = os.getenv("ADMIN_UPI_ID")

# ✅ MongoDB Connection
mongo_client = MongoClient(MONGO_URI)
db = mongo_client["EscrowDB"]
users = db["Users"]
deposits = db["Deposits"]
transactions = db["Transactions"]

# ✅ Telegram Bot Setup
app = Client("escrow_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# 🎯 /start - User Account Summary
@app.on_message(filters.command("start"))
def start(client, message):
    user_id = message.from_user.id
    user = users.find_one({"user_id": user_id})

    if not user:
        message.reply_text("🚀 **Welcome to Escrow Bot!**\n\n🔹 **You are not registered.**\n📌 Use `/register` to start.")
        return
    
    text = f"""
🔹 **Account Summary**
👤 **User:** {message.from_user.first_name}
🆔 **User ID:** {user_id}
💰 **Balance:** ₹{user['balance']}
📦 **Total Deals:** {transactions.count_documents({"buyer": user_id})}

📝 **Start a New Escrow:** /escrow
"""
    message.reply_text(text)

# 🔰 /register - Register User
@app.on_message(filters.command("register"))
def register(client, message):
    user_id = message.from_user.id
    if users.find_one({"user_id": user_id}):
        message.reply_text("✅ **You are already registered!**")
        return

    users.insert_one({"user_id": user_id, "balance": 0})
    message.reply_text("✅ **Registration Successful!**\n💰 Now deposit money using `/deposit`.")

# 🏦 /deposit - Deposit Money
@app.on_message(filters.command("deposit"))
def deposit(client, message):
    user_id = message.from_user.id
    data = message.text.split(" ")

    if len(data) < 2:
        message.reply_text("❌ **Usage:** /deposit 500")
        return

    amount = int(data[1])
    if amount <= 0:
        message.reply_text("❌ **Invalid amount!**")
        return

    deposit_id = f"DEP-{user_id}-{amount}"

    deposits.insert_one({
        "deposit_id": deposit_id,
        "user_id": user_id,
        "amount": amount,
        "status": "pending"
    })

    message.reply_text(f"✅ **Deposit Request Sent!**\n💰 **Amount:** ₹{amount}\n🏦 **Pay to:** `{ADMIN_UPI_ID}`\n\n📌 **After payment, click confirm:** `/confirm {deposit_id}`")
    client.send_message(ADMIN_ID, f"🔔 **New Deposit Request!**\n👤 User ID: {user_id}\n💰 Amount: ₹{amount}\n📌 **Approve:** /approve {deposit_id}\n❌ **Reject:** /reject {deposit_id}")

# ✅ /confirm - User Confirms Payment
@app.on_message(filters.command("confirm"))
def confirm_payment(client, message):
    user_id = message.from_user.id
    data = message.text.split(" ")

    if len(data) < 2:
        message.reply_text("❌ **Usage:** /confirm DEP-UserID-Amount")
        return

    deposit_id = data[1]
    deposit = deposits.find_one({"deposit_id": deposit_id, "user_id": user_id})

    if not deposit or deposit["status"] != "pending":
        message.reply_text("❌ **Invalid or already processed deposit!**")
        return

    client.send_message(ADMIN_ID, f"🔔 **User confirmed payment!**\n📌 Deposit ID: {deposit_id}\n👤 User: {user_id}\n✅ **Approve using:** /approve {deposit_id}")
    message.reply_text("⌛ **Waiting for Admin Approval...**")

# ✅ /approve - Admin Approves Deposit
@app.on_message(filters.command("approve"))
def approve_deposit(client, message):
    if message.from_user.id != ADMIN_ID:
        message.reply_text("❌ **You are not authorized!**")
        return

    data = message.text.split(" ")
    if len(data) < 2:
        message.reply_text("❌ **Usage:** /approve DEP-UserID-Amount")
        return

    deposit_id = data[1]
    deposit = deposits.find_one({"deposit_id": deposit_id})

    if not deposit or deposit["status"] != "pending":
        message.reply_text("❌ **Invalid or already processed deposit!**")
        return

    user_id = deposit["user_id"]
    amount = deposit["amount"]

    users.update_one({"user_id": user_id}, {"$inc": {"balance": amount}})
    deposits.update_one({"deposit_id": deposit_id}, {"$set": {"status": "approved"}})

    client.send_message(user_id, f"✅ **Deposit Approved!**\n💰 **New Balance:** ₹{users.find_one({'user_id': user_id})['balance']}")
    message.reply_text(f"✅ **Deposit Approved!**\n📌 Deposit ID: {deposit_id}")

# ❌ /reject - Admin Rejects Deposit
@app.on_message(filters.command("reject"))
def reject_deposit(client, message):
    if message.from_user.id != ADMIN_ID:
        message.reply_text("❌ **You are not authorized!**")
        return

    data = message.text.split(" ")
    if len(data) < 2:
        message.reply_text("❌ **Usage:** /reject DEP-UserID-Amount")
        return

    deposit_id = data[1]
    deposit = deposits.find_one({"deposit_id": deposit_id})

    if not deposit or deposit["status"] != "pending":
        message.reply_text("❌ **Invalid or already processed deposit!**")
        return

    deposits.update_one({"deposit_id": deposit_id}, {"$set": {"status": "rejected"}})
    client.send_message(deposit["user_id"], f"❌ **Deposit Rejected!**\n📌 Deposit ID: {deposit_id}")
    message.reply_text(f"❌ **Deposit Rejected!**\n📌 Deposit ID: {deposit_id}")

# 🔥 Run Bot
app.run()
