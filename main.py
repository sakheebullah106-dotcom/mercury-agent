import os
import io
import json
import time
import asyncio
import requests
from datetime import datetime, timedelta
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")
BOSS_CHAT_ID = os.environ.get("BOSS_CHAT_ID")

CLIENTS_FILE = "clients.json"
SCHEDULE_FILE = "schedule.json"
TRAINING_FILE = "mercury_training.json"


def load_json(filename):
    try:
        if os.path.exists(filename):
            with open(filename, "r") as f:
                return json.load(f)
    except Exception:
        pass
    return {}


def save_json(filename, data):
    try:
        with open(filename, "w") as f:
            json.dump(data, f)
    except Exception:
        pass


clients_db = load_json(CLIENTS_FILE)
schedule_db = load_json(SCHEDULE_FILE)
training_db = load_json(TRAINING_FILE)


MERCURY_SYSTEM = """You are MERCURY, a world-class client communication manager and business coordinator. You communicate EXACTLY like a real, experienced human account manager - warm, professional, and genuinely helpful.

YOUR PERSONALITY:
- You're friendly but professional - like a trusted business partner
- You remember details about each client and reference them naturally
- You never sound robotic, templated, or fake
- You use the client's name naturally in conversation
- You show genuine interest in their business success
- You're confident but never arrogant
- You handle objections gracefully with empathy
- You know when to be formal and when to be casual

COMMUNICATION RULES:
1. Always greet by name if known
2. Reference their specific business/industry
3. Show you understand their unique challenges
4. Offer specific solutions, not generic promises
5. Use contractions naturally (I'm, we'll, don't, can't)
6. Keep messages concise - busy people don't read novels
7. Always end with a clear next step or question
8. Match the client's communication style (formal/casual)
9. If they're frustrated, acknowledge it first before solving
10. Never use corporate jargon or buzzwords

CLIENT LIFECYCLE STAGES:
- NEW LEAD: First contact, introduce yourself
- INTERESTED: They replied, discuss their needs
- QUALIFIED: You know what they need, propose services
- PROPOSAL SENT: Waiting for their decision
- ACTIVE CLIENT: Working together, deliver and follow up
- REVISION: They want changes, handle gracefully
- COMPLETED: Job done, ask for feedback and referral
- FOLLOW UP: Check in after some time for repeat business

SCHEDULING AWARENESS:
- You know what tasks are due today
- You proactively remind about deadlines
- You suggest optimal times for follow-ups
- You keep track of client response patterns

NEVER DO:
- Never sound like a bot or AI
- Never use "Dear Sir/Madam"
- Never send walls of text
- Never make promises you can't keep
- Never ignore a client's concern
- Never be pushy or desperate
- Never use the word "utilize" or "leverage"
- Never start with "I hope this email finds you well" """


def try_gemini(prompt):
    url = (
        "https://generativelanguage.googleapis.com"
        "/v1beta/models/gemini-2.0-flash:generateContent"
        "?key=" + GEMINI_API_KEY
    )
    data = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.85,
            "maxOutputTokens": 8000
        }
    }
    r = requests.post(url, headers={"Content-Type": "application/json"}, json=data, timeout=120)
    r.raise_for_status()
    return r.json()["candidates"][0]["content"]["parts"][0]["text"]


def try_groq(prompt):
    data = {
        "model": "llama-3.3-70b-versatile",
        "messages": [
            {"role": "system", "content": MERCURY_SYSTEM},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.85,
        "max_tokens": 4000
    }
    r = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={"Authorization": "Bearer " + GROQ_API_KEY, "Content-Type": "application/json"},
        json=data, timeout=120
    )
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]


def try_openrouter(prompt):
    data = {
        "model": "meta-llama/llama-3.3-70b-instruct:free",
        "messages": [
            {"role": "system", "content": MERCURY_SYSTEM},
            {"role": "user", "content": prompt}
        ]
    }
    r = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={"Authorization": "Bearer " + OPENROUTER_API_KEY, "Content-Type": "application/json"},
        json=data, timeout=120
    )
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]


def ask_mercury(prompt):
    extra = ""
    if training_db.get("style"):
        extra += "\nCommunication style: " + training_db["style"]
    if training_db.get("rules"):
        extra += "\nSpecial rules: " + training_db["rules"]
    if training_db.get("samples"):
        extra += "\nMatch this tone:\n" + "\n---\n".join(training_db["samples"][-3:])
    full = MERCURY_SYSTEM + extra + "\n\nTASK:\n" + prompt
    errors = []
    if GEMINI_API_KEY and len(GEMINI_API_KEY) > 10:
        try:
            return try_gemini(full)
        except Exception as e:
            errors.append("G:" + str(e)[:60])
    if GROQ_API_KEY and len(GROQ_API_KEY) > 10:
        try:
            return try_groq(prompt + extra)
        except Exception as e:
            errors.append("Q:" + str(e)[:60])
    if OPENROUTER_API_KEY and len(OPENROUTER_API_KEY) > 10:
        try:
            return try_openrouter(prompt + extra)
        except Exception as e:
            errors.append("O:" + str(e)[:60])
    if errors:
        return "Error:\n" + "\n".join(errors)
    return "No API keys found."

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📨 MERCURY Agent v1.0\n"
        "Client Communication + Scheduler\n\n"
        "👤 CLIENT MANAGEMENT:\n"
        "/newclient [name] [niche] [contact] - Add client\n"
        "/clients - View all clients\n"
        "/client [name] - View client details\n"
        "/update [name] [status] - Update status\n"
        "/remove [name] - Remove client\n\n"
        "💬 COMMUNICATION:\n"
        "/reply [client name] [their message] - Draft reply\n"
        "/intro [client name] - First contact message\n"
        "/followup [client name] - Follow-up message\n"
        "/proposal [client name] [service] - Create proposal\n"
        "/deliver [client name] [what you delivered] - Delivery message\n"
        "/revision [client name] [feedback] - Handle revision\n"
        "/thankyou [client name] - Thank you + referral ask\n"
        "/cold [niche] - Cold outreach message\n\n"
        "⏰ SCHEDULER:\n"
        "/schedule - View today's schedule\n"
        "/addtask [time] [task] - Add task\n"
        "/routine - Set daily routine\n"
        "/remind [minutes] [task] - Set reminder\n"
        "/morning - Morning briefing\n"
        "/evening - Evening report\n\n"
        "🧠 TRAINING:\n"
        "/train [style] - Set communication style\n"
        "/trainsample [message example] - Give sample\n"
        "/trainrule [rule] - Add communication rule\n"
        "/trainstatus - View training\n"
        "/trainreset - Reset training\n\n"
        "💡 Or just type naturally:\n"
        "'reply to Ali who said he wants cheaper price'\n"
        "'draft a proposal for Sarah fitness coaching'\n"
        "'what should I say to a new restaurant lead'"
    )


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📨 MERCURY COMMANDS:\n\n"
        "👤 /newclient Ali restaurant ali@email.com\n"
        "/clients | /client Ali | /update Ali active | /remove Ali\n\n"
        "💬 /reply Ali he said price is too high\n"
        "/intro Ali | /followup Ali | /proposal Ali blog writing\n"
        "/deliver Ali 5 Instagram captions | /revision Ali wants shorter\n"
        "/thankyou Ali | /cold restaurants Lahore\n\n"
        "⏰ /schedule | /addtask 9am find leads\n"
        "/routine | /morning | /evening\n\n"
        "🧠 /train friendly casual | /trainsample [text]\n"
        "/trainrule always offer free sample first"
    )


async def new_client(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args or len(context.args) < 2:
        await update.message.reply_text(
            "❌ Format: /newclient [name] [niche] [contact]\n\n"
            "/newclient Ali restaurant ali@gmail.com\n"
            "/newclient Sarah fitness @sarah_fit\n"
            "/newclient John realestate john@company.com"
        )
        return
    uid = str(update.effective_user.id)
    name = context.args[0]
    details = " ".join(context.args[1:])
    if uid not in clients_db:
        clients_db[uid] = {}
    clients_db[uid][name.lower()] = {
        "name": name,
        "details": details,
        "status": "new_lead",
        "added": datetime.now().strftime("%Y-%m-%d"),
        "messages": [],
        "notes": ""
    }
    save_json(CLIENTS_FILE, clients_db)
    await update.message.reply_text(
        "✅ Client added!\n\n"
        "Name: " + name + "\n"
        "Details: " + details + "\n"
        "Status: NEW LEAD\n\n"
        "Next:\n"
        "/intro " + name + " - Draft first message\n"
        "/proposal " + name + " [service] - Create proposal"
    )


async def view_clients(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    if uid not in clients_db or not clients_db[uid]:
        await update.message.reply_text("📋 No clients yet.\n/newclient to add one!")
        return
    s = "📋 YOUR CLIENTS\n\n"
    for key, client in clients_db[uid].items():
        status_emoji = {
            "new_lead": "🆕", "interested": "👀", "qualified": "✅",
            "proposal_sent": "📤", "active": "🟢", "revision": "🔄",
            "completed": "✅", "follow_up": "📞"
        }.get(client["status"], "⚪")
        s += status_emoji + " " + client["name"] + " [" + client["status"].upper() + "]\n"
        s += "   " + client["details"][:50] + "\n\n"
    s += "Total: " + str(len(clients_db[uid])) + " clients"
    await update.message.reply_text(s)


async def view_client(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("❌ /client Ali")
        return
    uid = str(update.effective_user.id)
    name = context.args[0].lower()
    if uid not in clients_db or name not in clients_db[uid]:
        await update.message.reply_text("❌ Client not found. /clients to see all.")
        return
    c = clients_db[uid][name]
    s = "👤 CLIENT: " + c["name"] + "\n\n"
    s += "Details: " + c["details"] + "\n"
    s += "Status: " + c["status"].upper() + "\n"
    s += "Added: " + c.get("added", "unknown") + "\n"
    if c.get("notes"):
        s += "Notes: " + c["notes"] + "\n"
    if c.get("messages"):
        s += "\nMessage History:\n"
        for msg in c["messages"][-5:]:
            s += "• " + msg[:80] + "\n"
    await update.message.reply_text(s)


async def update_client(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args or len(context.args) < 2:
        await update.message.reply_text(
            "❌ /update [name] [status]\n\n"
            "Statuses: new_lead, interested, qualified,\n"
            "proposal_sent, active, revision, completed, follow_up"
        )
        return
    uid = str(update.effective_user.id)
    name = context.args[0].lower()
    new_status = context.args[1].lower()
    if uid not in clients_db or name not in clients_db[uid]:
        await update.message.reply_text("❌ Client not found.")
        return
    clients_db[uid][name]["status"] = new_status
    save_json(CLIENTS_FILE, clients_db)
    await update.message.reply_text("✅ " + name.title() + " → " + new_status.upper())


async def remove_client(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("❌ /remove Ali")
        return
    uid = str(update.effective_user.id)
    name = context.args[0].lower()
    if uid in clients_db and name in clients_db[uid]:
        del clients_db[uid][name]
        save_json(CLIENTS_FILE, clients_db)
        await update.message.reply_text("🗑️ " + name.title() + " removed!")
    else:
        await update.message.reply_text("❌ Client not found.")

def get_client_context(uid, name):
    if uid in clients_db and name.lower() in clients_db[uid]:
        c = clients_db[uid][name.lower()]
        return (
            "Client: " + c["name"] + "\n"
            "Business/Niche: " + c["details"] + "\n"
            "Status: " + c["status"] + "\n"
            "Notes: " + c.get("notes", "none")
        )
    return "Client: " + name


async def reply_client(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args or len(context.args) < 2:
        await update.message.reply_text("❌ /reply Ali he said price is too high")
        return
    uid = str(update.effective_user.id)
    name = context.args[0]
    their_msg = " ".join(context.args[1:])
    ctx = get_client_context(uid, name)
    await update.message.reply_text("💬 Drafting reply to " + name + "...")
    prompt = (
        "Draft a reply to this client:\n\n"
        "CLIENT INFO:\n" + ctx + "\n\n"
        "THEY SAID:\n\"" + their_msg + "\"\n\n"
        "Write 2 reply versions:\n"
        "VERSION 1: Short casual reply (for WhatsApp/DM)\n"
        "VERSION 2: Professional reply (for email)\n\n"
        "Rules:\n"
        "- Sound like a real human, warm and understanding\n"
        "- Address their concern directly\n"
        "- Offer a solution or next step\n"
        "- Keep it concise\n"
        "- Use their name naturally\n"
        "- End with a clear call-to-action"
    )
    result = ask_mercury(prompt)
    await update.message.reply_text(result)
    if uid in clients_db and name.lower() in clients_db[uid]:
        clients_db[uid][name.lower()]["messages"].append("They: " + their_msg[:100])
        save_json(CLIENTS_FILE, clients_db)


async def intro_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("❌ /intro Ali")
        return
    uid = str(update.effective_user.id)
    name = context.args[0]
    ctx = get_client_context(uid, name)
    await update.message.reply_text("✍️ Drafting intro for " + name + "...")
    prompt = (
        "Write the FIRST contact message to this potential client:\n\n"
        "CLIENT INFO:\n" + ctx + "\n\n"
        "Create 3 versions:\n"
        "1. SHORT DM (WhatsApp/Instagram) - under 100 words\n"
        "2. EMAIL - subject line + body\n"
        "3. COMMENT/REPLY on their post\n\n"
        "Rules:\n"
        "- Show you know their business\n"
        "- Mention a specific problem you can solve\n"
        "- Offer value upfront (free sample/tip)\n"
        "- Sound genuinely interested, not salesy\n"
        "- Clear next step\n"
        "- Human warm tone"
    )
    result = ask_mercury(prompt)
    await update.message.reply_text(result)


async def followup_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("❌ /followup Ali")
        return
    uid = str(update.effective_user.id)
    name = context.args[0]
    ctx = get_client_context(uid, name)
    await update.message.reply_text("📞 Drafting follow-up...")
    prompt = (
        "Write a follow-up message for:\n\n" + ctx + "\n\n"
        "Create 2 versions:\n"
        "1. GENTLE follow-up (2-3 days no reply)\n"
        "2. FINAL follow-up (1 week no reply)\n\n"
        "Sound natural, not desperate. Add new value in each follow-up."
    )
    result = ask_mercury(prompt)
    await update.message.reply_text(result)


async def proposal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args or len(context.args) < 2:
        await update.message.reply_text("❌ /proposal Ali blog writing monthly")
        return
    uid = str(update.effective_user.id)
    name = context.args[0]
    service = " ".join(context.args[1:])
    ctx = get_client_context(uid, name)
    await update.message.reply_text("📝 Creating proposal...")
    prompt = (
        "Create a service proposal:\n\n"
        "CLIENT:\n" + ctx + "\n\n"
        "SERVICE: " + service + "\n\n"
        "Include:\n"
        "1. GREETING - personalized\n"
        "2. UNDERSTANDING - show you get their needs\n"
        "3. SOLUTION - what you'll deliver\n"
        "4. DELIVERABLES - exact items with quantities\n"
        "5. TIMELINE - when they'll get it\n"
        "6. PRICING - with options (basic/standard/premium)\n"
        "7. WHY YOU - brief credibility\n"
        "8. NEXT STEP - clear CTA\n"
        "9. GUARANTEE - risk reversal\n\n"
        "Keep it under 300 words. Professional but warm.\n"
        "Make pricing competitive for Pakistan-based freelancer."
    )
    result = ask_mercury(prompt)
    await update.message.reply_text(result)
    if uid in clients_db and name.lower() in clients_db[uid]:
        clients_db[uid][name.lower()]["status"] = "proposal_sent"
        save_json(CLIENTS_FILE, clients_db)


async def deliver_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args or len(context.args) < 2:
        await update.message.reply_text("❌ /deliver Ali 5 Instagram captions")
        return
    uid = str(update.effective_user.id)
    name = context.args[0]
    what = " ".join(context.args[1:])
    ctx = get_client_context(uid, name)
    await update.message.reply_text("📤 Drafting delivery message...")
    prompt = (
        "Write a delivery message:\n\n"
        "CLIENT:\n" + ctx + "\n"
        "DELIVERED: " + what + "\n\n"
        "Include:\n"
        "- Warm greeting\n"
        "- What's included in delivery\n"
        "- Brief explanation of what you created\n"
        "- Ask for feedback\n"
        "- Mention revision availability\n"
        "- Suggest next steps (more work?)\n\n"
        "Short, professional, friendly."
    )
    result = ask_mercury(prompt)
    await update.message.reply_text(result)
    if uid in clients_db and name.lower() in clients_db[uid]:
        clients_db[uid][name.lower()]["status"] = "active"
        save_json(CLIENTS_FILE, clients_db)


async def revision_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args or len(context.args) < 2:
        await update.message.reply_text("❌ /revision Ali wants shorter captions")
        return
    name = context.args[0]
    feedback = " ".join(context.args[1:])
    uid = str(update.effective_user.id)
    ctx = get_client_context(uid, name)
    await update.message.reply_text("🔄 Handling revision...")
    prompt = (
        "Handle a revision request:\n\n"
        "CLIENT:\n" + ctx + "\n"
        "THEIR FEEDBACK: \"" + feedback + "\"\n\n"
        "Write a response that:\n"
        "- Acknowledges their feedback positively\n"
        "- Shows you understand what they want changed\n"
        "- Gives a timeline for the revision\n"
        "- Stays professional and positive\n"
        "- Doesn't sound defensive\n\n"
        "Also provide:\n"
        "- LOKI TASK: What to tell LOKI to redo\n"
        "  (clear instructions for the revision)"
    )
    result = ask_mercury(prompt)
    await update.message.reply_text(result)


async def thankyou_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("❌ /thankyou Ali")
        return
    name = context.args[0]
    uid = str(update.effective_user.id)
    ctx = get_client_context(uid, name)
    await update.message.reply_text("🙏 Drafting thank you...")
    prompt = (
        "Write a thank-you message after completing work:\n\n"
        "CLIENT:\n" + ctx + "\n\n"
        "Include:\n"
        "- Genuine thanks for the opportunity\n"
        "- Brief mention of what was delivered\n"
        "- Ask for a testimonial/review (naturally)\n"
        "- Ask for referral (subtly)\n"
        "- Mention future services available\n"
        "- Keep door open for repeat business\n\n"
        "Warm, genuine, not too long."
    )
    result = ask_mercury(prompt)
    await update.message.reply_text(result)


async def cold_outreach(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("❌ /cold restaurants Lahore")
        return
    niche = " ".join(context.args)
    await update.message.reply_text("❄️ Creating cold outreach...")
    prompt = (
        "Create cold outreach messages for: " + niche + "\n\n"
        "5 different templates:\n"
        "1. Instagram DM\n"
        "2. Facebook message\n"
        "3. Email\n"
        "4. WhatsApp\n"
        "5. LinkedIn message\n\n"
        "Each must:\n"
        "- Sound personal, not mass-sent\n"
        "- Reference their specific business type\n"
        "- Offer specific value\n"
        "- Be under 80 words\n"
        "- Have clear CTA\n"
        "- Sound like a real person"
    )
    result = ask_mercury(prompt)
    await update.message.reply_text(result)

async def view_schedule(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    today = datetime.now().strftime("%Y-%m-%d")
    if uid not in schedule_db:
        schedule_db[uid] = {}
    tasks = schedule_db[uid].get(today, [])
    if not tasks:
        await update.message.reply_text(
            "📅 No tasks for today.\n/addtask 9am Find restaurant leads\n/routine to set daily routine"
        )
        return
    s = "📅 TODAY'S SCHEDULE\n" + today + "\n\n"
    for t in tasks:
        done = "✅" if t.get("done") else "⬜"
        s += done + " " + t["time"] + " - " + t["task"] + "\n"
    await update.message.reply_text(s)


async def add_task(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args or len(context.args) < 2:
        await update.message.reply_text("❌ /addtask 9am Find restaurant leads")
        return
    uid = str(update.effective_user.id)
    today = datetime.now().strftime("%Y-%m-%d")
    task_time = context.args[0]
    task_desc = " ".join(context.args[1:])
    if uid not in schedule_db:
        schedule_db[uid] = {}
    if today not in schedule_db[uid]:
        schedule_db[uid][today] = []
    schedule_db[uid][today].append({"time": task_time, "task": task_desc, "done": False})
    save_json(SCHEDULE_FILE, schedule_db)
    await update.message.reply_text("✅ Task added: " + task_time + " - " + task_desc)


async def set_routine(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⏰ Setting up daily routine...")
    prompt = (
        "Create an optimal daily schedule for a freelance content writing agency owner.\n\n"
        "The system has these agents:\n"
        "- HUNTER: Finds leads and potential clients\n"
        "- MERCURY: Handles client communication\n"
        "- LOKI: Writes content\n\n"
        "Create a schedule from 9 AM to 9 PM:\n"
        "- When to use HUNTER to find leads\n"
        "- When to send outreach messages\n"
        "- When to check client replies\n"
        "- When to create content with LOKI\n"
        "- When to deliver work\n"
        "- When to follow up\n"
        "- Break times\n\n"
        "Format:\n"
        "9:00 AM - [task]\n"
        "9:30 AM - [task]\n"
        "...\n\n"
        "Make it practical and not overwhelming.\n"
        "Focus on revenue-generating activities first."
    )
    result = ask_mercury(prompt)
    await update.message.reply_text(result)


async def morning_briefing(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    client_count = len(clients_db.get(uid, {}))
    active = sum(1 for c in clients_db.get(uid, {}).values() if c["status"] == "active")
    pending = sum(1 for c in clients_db.get(uid, {}).values() if c["status"] in ["new_lead", "interested", "proposal_sent"])
    await update.message.reply_text("☀️ Generating morning briefing...")
    prompt = (
        "Create a morning briefing for the agency owner.\n\n"
        "Current stats:\n"
        "- Total clients: " + str(client_count) + "\n"
        "- Active clients: " + str(active) + "\n"
        "- Pending leads: " + str(pending) + "\n\n"
        "Include:\n"
        "1. Good morning greeting\n"
        "2. Today's priority tasks (what to do first)\n"
        "3. Which clients need attention\n"
        "4. Leads to follow up with\n"
        "5. Content to create today\n"
        "6. Motivational note\n\n"
        "Keep it brief and actionable. Like a real assistant briefing the boss."
    )
    result = ask_mercury(prompt)
    await update.message.reply_text(result)


async def evening_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    client_count = len(clients_db.get(uid, {}))
    await update.message.reply_text("🌙 Generating evening report...")
    prompt = (
        "Create an evening report for the agency owner.\n\n"
        "Stats: " + str(client_count) + " total clients\n\n"
        "Include:\n"
        "1. What should have been accomplished today\n"
        "2. Tomorrow's priorities\n"
        "3. Clients to follow up with tomorrow\n"
        "4. New strategies to try\n"
        "5. Weekly goal check\n"
        "6. Encouraging closing note\n\n"
        "Brief and motivating."
    )
    result = ask_mercury(prompt)
    await update.message.reply_text(result)


async def train(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("🧠 /train friendly casual Urdu English mix")
        return
    training_db["style"] = " ".join(context.args)
    save_json(TRAINING_FILE, training_db)
    await update.message.reply_text("🧠 Style: " + training_db["style"] + " ✅")


async def trainsample(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("📝 /trainsample [paste a message you like]")
        return
    if "samples" not in training_db:
        training_db["samples"] = []
    training_db["samples"].append(" ".join(context.args)[:2000])
    save_json(TRAINING_FILE, training_db)
    await update.message.reply_text("🧠 Sample #" + str(len(training_db["samples"])) + " saved!")


async def trainrule(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("📋 /trainrule always offer free sample first")
        return
    rule = " ".join(context.args)
    if "rules" in training_db:
        training_db["rules"] += " | " + rule
    else:
        training_db["rules"] = rule
    save_json(TRAINING_FILE, training_db)
    await update.message.reply_text("🧠 Rule: " + rule + " ✅")


async def trainstatus(update: Update, context: ContextTypes.DEFAULT_TYPE):
    s = "🧠 MERCURY TRAINING\n\n"
    if training_db.get("style"):
        s += "🎨 Style: " + training_db["style"] + "\n"
    if training_db.get("samples"):
        s += "📝 Samples: " + str(len(training_db["samples"])) + "\n"
    if training_db.get("rules"):
        s += "📋 Rules: " + training_db["rules"] + "\n"
    if len(s) < 30:
        s += "No training yet. /train to start!"
    await update.message.reply_text(s)


async def trainreset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    training_db.clear()
    save_json(TRAINING_FILE, training_db)
    await update.message.reply_text("🗑️ Training reset!")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if not text:
        return
    lower = text.lower()
    if any(w in lower for w in ["reply", "respond", "answer", "what should i say"]):
        await update.message.reply_text("💬 Drafting...")
        prompt = "Help draft a client communication:\n\n" + text + "\n\nGive 2 versions: casual DM and professional email."
        result = ask_mercury(prompt)
        await update.message.reply_text(result)
    elif any(w in lower for w in ["proposal", "offer", "quote", "pitch"]):
        await update.message.reply_text("📝 Creating...")
        prompt = "Create a service proposal:\n\n" + text
        result = ask_mercury(prompt)
        await update.message.reply_text(result)
    elif any(w in lower for w in ["follow", "check in", "reminder"]):
        await update.message.reply_text("📞 Drafting...")
        prompt = "Create a follow-up message:\n\n" + text
        result = ask_mercury(prompt)
        await update.message.reply_text(result)
    elif any(w in lower for w in ["schedule", "plan", "routine", "task"]):
        await update.message.reply_text("📅 Planning...")
        prompt = "Help plan/schedule:\n\n" + text
        result = ask_mercury(prompt)
        await update.message.reply_text(result)
    else:
        await update.message.reply_text("📨 Working...")
        prompt = text + "\n\nRespond as a client communication expert. Give actionable advice."
        result = ask_mercury(prompt)
        await update.message.reply_text(result)


async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    s = "📨 MERCURY STATUS\n\n"
    e = 0
    if GEMINI_API_KEY and len(GEMINI_API_KEY) > 10:
        s += "🟢 Gemini ON\n"; e += 1
    if GROQ_API_KEY and len(GROQ_API_KEY) > 10:
        s += "🔵 Groq ON\n"; e += 1
    if OPENROUTER_API_KEY and len(OPENROUTER_API_KEY) > 10:
        s += "🟡 OpenRouter ON\n"; e += 1
    s += "Engines: " + str(e) + "/3\n\n"
    client_count = len(clients_db.get(uid, {}))
    s += "👤 Clients: " + str(client_count) + "\n"
    if training_db.get("style"):
        s += "🧠 Training: Active\n"
    else:
        s += "🧠 Training: Not set\n"
    await update.message.reply_text(s)


def main():
    print("MERCURY Agent v1.0 Starting...")
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    cmds = {
        "start": start, "help": help_cmd, "status": status,
        "newclient": new_client, "clients": view_clients,
        "client": view_client, "update": update_client, "remove": remove_client,
        "reply": reply_client, "intro": intro_message,
        "followup": followup_message, "proposal": proposal,
        "deliver": deliver_message, "revision": revision_message,
        "thankyou": thankyou_message, "cold": cold_outreach,
        "schedule": view_schedule, "addtask": add_task,
        "routine": set_routine, "morning": morning_briefing, "evening": evening_report,
        "train": train, "trainsample": trainsample,
        "trainrule": trainrule, "trainstatus": trainstatus, "trainreset": trainreset
    }
    for n, f in cmds.items():
        app.add_handler(CommandHandler(n, f))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print("MERCURY Agent v1.0 LIVE!")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
