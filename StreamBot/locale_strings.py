"""
UI strings for /start welcome, premium entry keyboard, and related screens.
English copies mirror StreamBot/config.py; other languages are user-facing translations.
"""

from __future__ import annotations

SUPPORTED_LANGS = frozenset({"en", "id", "ms", "ar", "es", "zh"})


def normalize_lang(code: str | None) -> str:
    if not code or not isinstance(code, str):
        return "en"
    c = code.strip().lower()
    if c in SUPPORTED_LANGS:
        return c
    return "en"


def t(lang: str, key: str, **kwargs) -> str:
    lang = normalize_lang(lang)
    pack = MESSAGES.get(lang) or MESSAGES["en"]
    text = pack.get(key)
    if text is None:
        text = MESSAGES["en"].get(key, key)
    return text.format(**kwargs) if kwargs else text


# Rows of (button_label with flag, lang_code) for the language picker on /start.
LANG_PICKER_ROWS: list[list[tuple[str, str]]] = [
    [
        ("🇬🇧 English", "en"),
        ("🇮🇩 Bahasa Indonesia", "id"),
        ("🇲🇾 Melayu", "ms"),
    ],
    [
        ("🇸🇦 العربية", "ar"),
        ("🇪🇸 Español", "es"),
        ("🇨🇳 简体中文", "zh"),
    ],
]


MESSAGES: dict[str, dict[str, str]] = {
    "en": {
        "start_premium": """Hello {mention}! 👋

🚀 **Welcome to the Ultimate Download Link Generator!**

📁 Send me any file to get a direct download link instantly.

🔐 **For Private Content:**
• Use `/login` once, then send the t.me post URL here
• Use `/logout` anytime to revoke access

🎯 **Ready to get started? Send me a file now!**
""",
        "start_non_premium": """Hello {mention}! 👋

🚀 **Welcome to the Ultimate Telegram Download Bot!**

We provide lightning-fast, direct download links for **any** file on Telegram — even from private channels!

🔒 **100% Secure & Private**
⚡ **High-Speed Global Servers**
📈 **Over 10,000+ files processed daily**

Tap the buttons below to see what we can do for you, or hit **🚀 GET STARTED** to unlock premium access instantly!
""",
        "help": """Here is how to use the bot:

- Send me any file to get a direct download link.
- To access files from private channels/groups you belong to, use /login and authenticate on the session generator, then send the t.me post URL here.
- Use /logout to revoke your session and invalidate your private links.
""",
        "about": """🤖 **Telegram Download Link Generator**

📦 **PyroFork Version:** {pyro_version}
☁️ **Deployed on:** [Koyeb](https://koyeb.com)
🔗 **Repository:** [GitHub]({github_url})

💡 **Features:**
• Direct download links for any file
• Private channel/group support via sessions
• Secure encrypted session storage
• Multi-token support for reliability

⚡ **Powered by:** Python, Pyrogram, and MongoDB
""",
        "features": """✨ **Premium Features:**

• **Direct Download Links**: Bypass Telegram's clunky app restrictions
• **Private Channel Access**: Get links for files in private channels via secure login
• **High Speed Streaming**: Stream videos directly in your browser without downloading
• **Unlimited Speed**: Enterprise-grade proxy servers for maximum bandwidth
• **Ad-Free Experience**: Smooth, uninterrupted downloads
""",
        "how_it_works": """🛠 **How It Works:**

**1️⃣ Public Files:**
Just forward or send any file to the bot. We'll reply instantly with a direct download link!

**2️⃣ Private Channels:**
• Type `/login` to securely authenticate your session
• Copy the message link from any private channel you're a member of
• Send the link to the bot — we'll generate your direct link!

**3️⃣ Stream Anywhere:**
Click the generated link to preview, stream, or download.
""",
        "pricing": """💰 **Premium Plans:**

Stop waiting. Unlock the full power of direct downloads and private channel access today!

• Flexible daily, weekly, and monthly passes
• Pay securely via Crypto (USDT) or UPI
• Instant automated activation

Tap **🚀 GET STARTED** below to view prices and upgrade instantly!
""",
        "premium_required": (
            "🔒 Premium required to use this bot.\n\n"
            "Tap the button below to buy premium."
        ),
        "btn_help": "❓ Help",
        "btn_about": "ℹ️ About",
        "btn_close": "✖️ Close",
        "premium_get_started": "🚀 GET STARTED",
        "premium_how_it_works": "📖 HOW IT WORKS",
        "premium_features": "💬 FEATURES",
        "premium_pricing": "💰 PRICING",
        "premium_help": "❓ HELP",
        "lang_saved": "Language updated.",
        "pay_choose_method": "Choose your payment method:",
        "pay_btn_crypto": "₿ USDT (BEP20)",
        "pay_btn_upi": "🇮🇳 UPI",
        "pay_method_crypto": "Crypto (USDT BEP20)",
        "pay_method_upi": "UPI",
        "pay_method_selected_header": "Selected payment method: {method}\n\n",
        "pay_choose_duration_hint": (
            "Choose subscription duration.\n"
            "You pay (price per day × days); only the total is rounded up to 2 decimals if needed."
        ),
        "pay_pricing_not_configured": "Pricing is not configured. Please contact the owner.",
        "pay_crypto_config_err": "Crypto pricing is not configured correctly. Please contact the owner.",
        "pay_upi_config_err": "UPI pricing is not configured correctly. Please contact the owner.",
        "pay_failed_start": "Failed to start purchase. Please try again.",
        "pay_amount_usdt": "Amount to pay: {amount} USDT (BEP20)",
        "pay_usdt_address_block": "USDT (BSC BEP20) address:\n{address}",
        "pay_amount_inr": "Amount to pay: INR {amount}",
        "pay_upi_block": "UPI ID:\n{upi_id}",
        "pay_invoice": (
            "Premium purchase started.\n\n"
            "Payment method: {method}\n"
            "Subscription days: {days}\n"
            "{amount_line}\n\n"
            "{address_block}\n\n"
            "After paying, tap **I PAID**.\n"
            "Then send your payment screenshot in this chat."
        ),
        "pay_btn_i_paid": "✅ I PAID",
        "pay_btn_cancel": "❌ CANCEL",
        "pay_btn_confirm": "✅ CONFIRM",
        "pay_marked_paid_intro": (
            "Payment marked as submitted.\n\n"
            "Upload your payment screenshot here (photo or document).\n"
            "After uploading, review your details and tap CONFIRM.\n"
        ),
        "pay_upload_screenshot_short": "Upload your payment screenshot here (photo or document).",
        "pay_step_inactive": "Payment step failed or this request is no longer active.",
        "pay_cancelled": "Purchase cancelled.",
        "err_screenshot_file": "Couldn't detect the screenshot file. Please send again.",
        "err_screenshot_upload": "Screenshot upload failed (step outdated). Please try again.",
        "err_unexpected_retry": "Unexpected error. Please try again.",
        "pay_review_header": "Review your payment details:\n\n",
        "pay_review_txn_id": "Transaction ID: {tid}",
        "pay_review_user_id": "User ID: {uid}",
        "pay_review_username": "Username: {username}",
        "pay_review_name": "Name: {name}",
        "pay_review_language": "Language: {tg_lang}",
        "pay_review_method": "Payment method: {method}",
        "pay_review_days": "Days: {days}",
        "pay_review_amount": "Amount: {amount}",
        "pay_submitted_wait": "Submitted to owner/admin for approval. Please wait.",
        "pay_fail_channel": (
            "Failed to send to transaction channel. Please verify TXN_CHNL_ID, bot permissions, and try again."
        ),
        "pay_txn_not_found": "Txn not found or expired.",
        "pay_already_submitted": "Already submitted. Please wait for admin confirmation.",
        "pay_txn_not_ready": "This txn is not ready for submission.",
        "pay_screenshot_missing": "Screenshot missing for this txn.",
        "pay_days_choice": "{n} day(s)",
        "premium_approved": (
            "✅ Premium approved!\n\n"
            "Your access is active now and will expire at: {expires}\n"
            "You can now use the bot."
        ),
        "premium_rejected": "❌ Premium payment rejected. You can try again.",
    },
    "id": {
        "start_premium": """Halo {mention}! 👋

🚀 **Selamat datang di Generator Tautan Unduhan!**

📁 Kirimkan file apa pun untuk mendapatkan tautan unduhan langsung.

🔐 **Untuk konten privat:**
• Gunakan `/login` sekali, lalu kirim URL postingan t.me ke sini
• Gunakan `/logout` kapan saja untuk mencabut akses

🎯 **Siap mulai? Kirim file sekarang!**
""",
        "start_non_premium": """Halo {mention}! 👋

🚀 **Selamat datang di Bot Unduhan Telegram!**

Kami menyediakan tautan unduhan super cepat untuk **semua** file di Telegram — termasuk dari channel privat!

🔒 **Aman & privat**
⚡ **Server cepat**
📈 **Ribuan file diproses setiap hari**

Gunakan tombol di bawah untuk info, atau **🚀 MULAI** untuk premium!
""",
        "help": """Cara pakai bot:

- Kirim file apa pun untuk tautan unduhan.
- Untuk channel/grup privat: `/login` di generator sesi, lalu kirim URL t.me postingan ke sini.
- `/logout` untuk cabut sesi dan tautan privat.
""",
        "about": """🤖 **Generator Tautan Unduhan Telegram**

📦 **Versi PyroFork:** {pyro_version}
☁️ **Hosting:** [Koyeb](https://koyeb.com)
🔗 **Repositori:** [GitHub]({github_url})

💡 **Fitur:**
• Tautan unduhan untuk semua file
• Channel privat lewat sesi
• Penyimpanan sesi terenkripsi
• Multi-token

⚡ **Dibangun dengan:** Python, Pyrogram, MongoDB
""",
        "features": """✨ **Fitur premium:**

• **Tautan langsung**: Lewati batasan aplikasi Telegram
• **Channel privat**: Lewat login aman
• **Streaming cepat**: Putar video di browser
• **Kecepatan tinggi**: Server proxy
• **Tanpa iklan**
""",
        "how_it_works": """🛠 **Cara kerja:**

**1️⃣ File publik:**
Teruskan atau kirim file — bot membalas dengan tautan unduhan.

**2️⃣ Channel privat:**
• `/login` untuk autentikasi
• Salin tautan postingan channel
• Kirim ke bot — kami buat tautan unduhan

**3️⃣ Streaming:**
Buka tautan untuk pratinjau atau unduh.
""",
        "pricing": """💰 **Paket premium:**

Aktifkan unduhan langsung dan akses channel privat!

• Paket harian/mingguan/bulanan
• Bayar dengan Crypto (USDT) atau UPI
• Aktivasi otomatis

Tekan **🚀 MULAI** di bawah untuk harga!
""",
        "premium_required": (
            "🔒 Premium diperlukan.\n\n"
            "Tekan tombol di bawah untuk membeli premium."
        ),
        "btn_help": "❓ Bantuan",
        "btn_about": "ℹ️ Tentang",
        "btn_close": "✖️ Tutup",
        "premium_get_started": "🚀 MULAI",
        "premium_how_it_works": "📖 CARA KERJA",
        "premium_features": "💬 FITUR",
        "premium_pricing": "💰 HARGA",
        "premium_help": "❓ BANTUAN",
        "lang_saved": "Bahasa diperbarui.",
        "pay_choose_method": "Pilih metode pembayaran:",
        "pay_btn_crypto": "₿ USDT (BEP20)",
        "pay_btn_upi": "🇮🇳 UPI",
        "pay_method_crypto": "Crypto (USDT BEP20)",
        "pay_method_upi": "UPI",
        "pay_method_selected_header": "Metode pembayaran: {method}\n\n",
        "pay_choose_duration_hint": (
            "Pilih durasi langganan.\n"
            "Anda membayar (harga per hari × hari); hanya total dibulatkan ke atas 2 desimal jika perlu."
        ),
        "pay_pricing_not_configured": "Harga belum dikonfigurasi. Hubungi pemilik.",
        "pay_crypto_config_err": "Harga crypto tidak benar. Hubungi pemilik.",
        "pay_upi_config_err": "Harga UPI tidak benar. Hubungi pemilik.",
        "pay_failed_start": "Gagal memulai pembelian. Coba lagi.",
        "pay_amount_usdt": "Jumlah dibayar: {amount} USDT (BEP20)",
        "pay_usdt_address_block": "Alamat USDT (BSC BEP20):\n{address}",
        "pay_amount_inr": "Jumlah dibayar: INR {amount}",
        "pay_upi_block": "UPI ID:\n{upi_id}",
        "pay_invoice": (
            "Pembelian premium dimulai.\n\n"
            "Metode: {method}\n"
            "Hari berlangganan: {days}\n"
            "{amount_line}\n\n"
            "{address_block}\n\n"
            "Setelah membayar, ketuk **SUDAH BAYAR**.\n"
            "Lalu kirim screenshot pembayaran di chat ini."
        ),
        "pay_btn_i_paid": "✅ SUDAH BAYAR",
        "pay_btn_cancel": "❌ BATAL",
        "pay_btn_confirm": "✅ KONFIRMASI",
        "pay_marked_paid_intro": (
            "Pembayaran ditandai terkirim.\n\n"
            "Unggah screenshot pembayaran (foto atau dokumen).\n"
            "Setelah itu periksa detail dan ketuk KONFIRMASI.\n"
        ),
        "pay_upload_screenshot_short": "Unggah screenshot pembayaran (foto atau dokumen).",
        "pay_step_inactive": "Langkah gagal atau permintaan tidak aktif.",
        "pay_cancelled": "Pembelian dibatalkan.",
        "err_screenshot_file": "File screenshot tidak terdeteksi. Kirim ulang.",
        "err_screenshot_upload": "Unggah gagal (langkah kedaluwarsa). Coba lagi.",
        "err_unexpected_retry": "Kesalahan tak terduga. Coba lagi.",
        "pay_review_header": "Periksa detail pembayaran:\n\n",
        "pay_review_txn_id": "ID transaksi: {tid}",
        "pay_review_user_id": "ID pengguna: {uid}",
        "pay_review_username": "Username: {username}",
        "pay_review_name": "Nama: {name}",
        "pay_review_language": "Bahasa: {tg_lang}",
        "pay_review_method": "Metode: {method}",
        "pay_review_days": "Hari: {days}",
        "pay_review_amount": "Jumlah: {amount}",
        "pay_submitted_wait": "Dikirim ke admin untuk persetujuan. Harap tunggu.",
        "pay_fail_channel": (
            "Gagal mengirim ke saluran transaksi. Periksa TXN_CHNL_ID, izin bot, dan coba lagi."
        ),
        "pay_txn_not_found": "Transaksi tidak ditemukan atau kedaluwarsa.",
        "pay_already_submitted": "Sudah dikirim. Tunggu konfirmasi admin.",
        "pay_txn_not_ready": "Transaksi belum siap dikirim.",
        "pay_screenshot_missing": "Screenshot tidak ada.",
        "pay_days_choice": "{n} hari",
        "premium_approved": (
            "✅ Premium disetujui!\n\n"
            "Akses aktif hingga: {expires}\n"
            "Anda dapat memakai bot sekarang."
        ),
        "premium_rejected": "❌ Pembayaran ditolak. Silakan coba lagi.",
    },
    "ms": {
        "start_premium": """Helo {mention}! 👋

🚀 **Selamat datang ke Penjana Pautan Muat Turun!**

📁 Hantar sebarang fail untuk pautan muat turun terus.

🔐 **Kandungan peribadi:**
• Guna `/login` sekali, kemudian hantar URL siaran t.me di sini
• Guna `/logout` untuk batalkan akses

🎯 **Bersedia? Hantar fail sekarang!**
""",
        "start_non_premium": """Helo {mention}! 👋

🚀 **Selamat datang ke Bot Muat Turun Telegram!**

Kami sediakan pautan muat turun pantas untuk **semua** fail — termasuk saluran peribadi!

🔒 **Selamat & peribadi**
⚡ **Pelayan pantas**
📈 **Ribuan fail diproses setiap hari**

Tekan butang di bawah atau **🚀 MULA** untuk premium!
""",
        "help": """Cara guna bot:

- Hantar fail untuk pautan muat turun.
- Saluran peribadi: `/login` di penjana sesi, kemudian hantar URL siaran t.me.
- `/logout` untuk batalkan sesi.
""",
        "about": """🤖 **Penjana Pautan Muat Turun Telegram**

📦 **Versi PyroFork:** {pyro_version}
☁️ **Hosting:** [Koyeb](https://koyeb.com)
🔗 **Repositori:** [GitHub]({github_url})

💡 **Ciri:**
• Pautan untuk semua fail
• Saluran peribadi melalui sesi
• Sesi disulitkan
• Multi-token

⚡ **Dibina dengan:** Python, Pyrogram, MongoDB
""",
        "features": """✨ **Ciri premium:**

• **Pautan terus**: Pintas sekatan Telegram
• **Saluran peribadi**: Log masuk selamat
• **Strim pantas**: Main video dalam pelayar
• **Kelajuan tinggi**
• **Tanpa iklan**
""",
        "how_it_works": """🛠 **Cara ia berfungsi:**

**1️⃣ Fail awam:**
Hantar atau teruskan fail — bot balas dengan pautan.

**2️⃣ Saluran peribadi:**
• `/login` untuk pengesahan
• Salin pautan siaran
• Hantar ke bot

**3️⃣ Strim:**
Buka pautan untuk pratonton atau muat turun.
""",
        "pricing": """💰 **Pelan premium:**

Buka kuasa muat turun dan akses saluran peribadi!

• Pas harian/mingguan/bulanan
• Bayar Crypto (USDT) atau UPI
• Pengaktifan automatik

Tekan **🚀 MULA** untuk harga!
""",
        "premium_required": (
            "🔒 Premium diperlukan.\n\n"
            "Tekan butang di bawah untuk beli premium."
        ),
        "btn_help": "❓ Bantuan",
        "btn_about": "ℹ️ Tentang",
        "btn_close": "✖️ Tutup",
        "premium_get_started": "🚀 MULA",
        "premium_how_it_works": "📖 CARA KERJA",
        "premium_features": "💬 CIRI",
        "premium_pricing": "💰 HARGA",
        "premium_help": "❓ BANTUAN",
        "lang_saved": "Bahasa dikemas kini.",
        "pay_choose_method": "Pilih kaedah pembayaran:",
        "pay_btn_crypto": "₿ USDT (BEP20)",
        "pay_btn_upi": "🇮🇳 UPI",
        "pay_method_crypto": "Crypto (USDT BEP20)",
        "pay_method_upi": "UPI",
        "pay_method_selected_header": "Kaedah pembayaran: {method}\n\n",
        "pay_choose_duration_hint": (
            "Pilih tempoh langganan.\n"
            "Anda bayar (harga sehari × hari); hanya jumlah dibundarkan ke atas 2 perpuluhan jika perlu."
        ),
        "pay_pricing_not_configured": "Harga tidak dikonfigurasi. Hubungi pemilik.",
        "pay_crypto_config_err": "Harga crypto tidak betul. Hubungi pemilik.",
        "pay_upi_config_err": "Harga UPI tidak betul. Hubungi pemilik.",
        "pay_failed_start": "Gagal mulakan pembelian. Cuba lagi.",
        "pay_amount_usdt": "Jumlah bayaran: {amount} USDT (BEP20)",
        "pay_usdt_address_block": "Alamat USDT (BSC BEP20):\n{address}",
        "pay_amount_inr": "Jumlah bayaran: INR {amount}",
        "pay_upi_block": "ID UPI:\n{upi_id}",
        "pay_invoice": (
            "Pembelian premium dimulakan.\n\n"
            "Kaedah: {method}\n"
            "Hari langganan: {days}\n"
            "{amount_line}\n\n"
            "{address_block}\n\n"
            "Selepas bayar, ketik **SUDAH BAYAR**.\n"
            "Kemudian hantar tangkapan skrin pembayaran di sini."
        ),
        "pay_btn_i_paid": "✅ SUDAH BAYAR",
        "pay_btn_cancel": "❌ BATAL",
        "pay_btn_confirm": "✅ SAHKAN",
        "pay_marked_paid_intro": (
            "Pembayaran ditanda dihantar.\n\n"
            "Muat naik tangkapan skrin (foto atau dokumen).\n"
            "Kemudian semak butiran dan ketik SAHKAN.\n"
        ),
        "pay_upload_screenshot_short": "Muat naik tangkapan skrin pembayaran (foto atau dokumen).",
        "pay_step_inactive": "Langkah gagal atau permintaan tidak aktif.",
        "pay_cancelled": "Pembelian dibatalkan.",
        "err_screenshot_file": "Tidak dapat mengesan fail. Hantar semula.",
        "err_screenshot_upload": "Muat naik gagal. Cuba lagi.",
        "err_unexpected_retry": "Ralat tidak dijangka. Cuba lagi.",
        "pay_review_header": "Semak butiran pembayaran:\n\n",
        "pay_review_txn_id": "ID transaksi: {tid}",
        "pay_review_user_id": "ID pengguna: {uid}",
        "pay_review_username": "Username: {username}",
        "pay_review_name": "Nama: {name}",
        "pay_review_language": "Bahasa: {tg_lang}",
        "pay_review_method": "Kaedah: {method}",
        "pay_review_days": "Hari: {days}",
        "pay_review_amount": "Jumlah: {amount}",
        "pay_submitted_wait": "Dihantar kepada admin. Sila tunggu.",
        "pay_fail_channel": (
            "Gagal hantar ke saluran transaksi. Semak TXN_CHNL_ID, kebenaran bot, dan cuba lagi."
        ),
        "pay_txn_not_found": "Transaksi tidak dijumpai atau tamat tempoh.",
        "pay_already_submitted": "Sudah dihantar. Tunggu pengesahan admin.",
        "pay_txn_not_ready": "Transaksi belum sedia.",
        "pay_screenshot_missing": "Tangkapan skrin tiada.",
        "pay_days_choice": "{n} hari",
        "premium_approved": (
            "✅ Premium diluluskan!\n\n"
            "Akses aktif sehingga: {expires}\n"
            "Anda boleh guna bot sekarang."
        ),
        "premium_rejected": "❌ Pembayaran ditolak. Cuba lagi.",
    },
    "ar": {
        "start_premium": """مرحبًا {mention}! 👋

🚀 **مرحبًا بك في مولّد روابط التحميل!**

📁 أرسل أي ملف للحصول على رابط تحميل مباشر.

🔐 **للمحتوى الخاص:**
• استخدم `/login` مرة واحدة، ثم أرسل رابط منشور t.me هنا
• استخدم `/logout` لإلغاء الوصول

🎯 **جاهز؟ أرسل ملفًا الآن!**
""",
        "start_non_premium": """مرحبًا {mention}! 👋

🚀 **مرحبًا بك في بوت تحميل تيليجرام!**

نوفر روابط تحميل سريعة لـ **أي** ملف — حتى من القنوات الخاصة!

🔒 **آمن وخاص**
⚡ **خوادم سريعة**
📈 **آلاف الملفات يوميًا**

استخدم الأزرار أدناه أو **🚀 ابدأ** للاشتراك المميز!
""",
        "help": """طريقة الاستخدام:

- أرسل أي ملف للحصول على رابط.
- للقنوات الخاصة: `/login` في مولّد الجلسة، ثم أرسل رابط المنشور.
- `/logout` لإلغاء الجلسة والروابط الخاصة.
""",
        "about": """🤖 **مولّد روابط تحميل تيليجرام**

📦 **إصدار PyroFork:** {pyro_version}
☁️ **الاستضافة:** [Koyeb](https://koyeb.com)
🔗 **المستودع:** [GitHub]({github_url})

💡 **الميزات:**
• روابط مباشرة لأي ملف
• قنوات خاصة عبر الجلسات
• تخزين جلسة مشفّر
• دعم عدة توكنات

⚡ **باستخدام:** Python و Pyrogram و MongoDB
""",
        "features": """✨ **ميزات مميزة:**

• **روابط مباشرة**: تجاوز قيود التطبيق
• **قنوات خاصة**: عبر تسجيل دخول آمن
• **بث سريع**: في المتصفح
• **سرعة عالية**
• **بدون إعلانات**
""",
        "how_it_works": """🛠 **كيف يعمل:**

**1️⃣ ملفات عامة:**
أرسل أو أعد توجيه ملف — نرسل رابط التحميل.

**2️⃣ قنوات خاصة:**
• `/login` للمصادقة
• انسخ رابط المنشور
• أرسله للبوت

**3️⃣ البث:**
افتح الرابط للمعاينة أو التحميل.
""",
        "pricing": """💰 **خطط مميزة:**

فعّل التحميل المباشر والوصول للقنوات الخاصة!

• خطط يومية/أسبوعية/شهرية
• دفع عبر USDT أو UPI
• تفعيل تلقائي

اضغط **🚀 ابدأ** أدناه للأسعار!
""",
        "premium_required": (
            "🔒 يلزم اشتراك مميز.\n\n"
            "اضغط الزر أدناه للشراء."
        ),
        "btn_help": "❓ مساعدة",
        "btn_about": "ℹ️ حول",
        "btn_close": "✖️ إغلاق",
        "premium_get_started": "🚀 ابدأ",
        "premium_how_it_works": "📖 كيف يعمل",
        "premium_features": "💬 الميزات",
        "premium_pricing": "💰 الأسعار",
        "premium_help": "❓ مساعدة",
        "lang_saved": "تم تحديث اللغة.",
        "pay_choose_method": "اختر طريقة الدفع:",
        "pay_btn_crypto": "₿ USDT (BEP20)",
        "pay_btn_upi": "🇮🇳 UPI",
        "pay_method_crypto": "عملة (USDT BEP20)",
        "pay_method_upi": "UPI",
        "pay_method_selected_header": "طريقة الدفع: {method}\n\n",
        "pay_choose_duration_hint": (
            "اختر مدة الاشتراك.\n"
            "تدفع (السعر لليوم × الأيام)؛ يُقرب المجموع لأعلى منزلتين عشريتين عند الحاجة."
        ),
        "pay_pricing_not_configured": "الأسعار غير مضبوطة. راسل المالك.",
        "pay_crypto_config_err": "سعر العملة غير صحيح. راسل المالك.",
        "pay_upi_config_err": "سعر UPI غير صحيح. راسل المالك.",
        "pay_failed_start": "تعذر بدء الشراء. حاول مرة أخرى.",
        "pay_amount_usdt": "المبلغ: {amount} USDT (BEP20)",
        "pay_usdt_address_block": "عنوان USDT (BSC BEP20):\n{address}",
        "pay_amount_inr": "المبلغ: INR {amount}",
        "pay_upi_block": "معرّف UPI:\n{upi_id}",
        "pay_invoice": (
            "بدء شراء بريميوم.\n\n"
            "الطريقة: {method}\n"
            "أيام الاشتراك: {days}\n"
            "{amount_line}\n\n"
            "{address_block}\n\n"
            "بعد الدفع اضغط **دفعت**.\n"
            "ثم أرسل لقطة شاشة للدفع هنا."
        ),
        "pay_btn_i_paid": "✅ دفعت",
        "pay_btn_cancel": "❌ إلغاء",
        "pay_btn_confirm": "✅ تأكيد",
        "pay_marked_paid_intro": (
            "تم تسجيل الدفع.\n\n"
            "ارفع لقطة الشاشة (صورة أو مستند).\n"
            "ثم راجع التفاصيل واضغط تأكيد.\n"
        ),
        "pay_upload_screenshot_short": "ارفع لقطة شاشة الدفع (صورة أو مستند).",
        "pay_step_inactive": "فشلت الخطوة أو انتهت الجلسة.",
        "pay_cancelled": "أُلغي الشراء.",
        "err_screenshot_file": "تعذر قراءة الملف. أرسل مرة أخرى.",
        "err_screenshot_upload": "فشل الرفع. حاول مرة أخرى.",
        "err_unexpected_retry": "خطأ غير متوقع. حاول مرة أخرى.",
        "pay_review_header": "راجع تفاصيل الدفع:\n\n",
        "pay_review_txn_id": "رقم العملية: {tid}",
        "pay_review_user_id": "معرّف المستخدم: {uid}",
        "pay_review_username": "المستخدم: {username}",
        "pay_review_name": "الاسم: {name}",
        "pay_review_language": "اللغة: {tg_lang}",
        "pay_review_method": "الطريقة: {method}",
        "pay_review_days": "الأيام: {days}",
        "pay_review_amount": "المبلغ: {amount}",
        "pay_submitted_wait": "أُرسل للمسؤول للموافقة. انتظر من فضلك.",
        "pay_fail_channel": (
            "فشل الإرسال لقناة المعاملات. تحقق من TXN_CHNL_ID وصلاحيات البوت."
        ),
        "pay_txn_not_found": "العملية غير موجودة أو منتهية.",
        "pay_already_submitted": "أُرسلت مسبقاً. انتظر تأكيد المسؤول.",
        "pay_txn_not_ready": "العملية غير جاهزة.",
        "pay_screenshot_missing": "لا توجد لقطة شاشة.",
        "pay_days_choice": "{n} يوماً",
        "premium_approved": (
            "✅ تمت الموافقة على البريميوم!\n\n"
            "صلاحيتك نشطة حتى: {expires}\n"
            "يمكنك استخدام البوت الآن."
        ),
        "premium_rejected": "❌ تم رفض الدفع. يمكنك المحاولة مرة أخرى.",
    },
    "es": {
        "start_premium": """¡Hola {mention}! 👋

🚀 **¡Bienvenido al generador de enlaces de descarga!**

📁 Envíame cualquier archivo para obtener un enlace directo.

🔐 **Contenido privado:**
• Usa `/login` una vez y luego envía la URL del post de t.me
• Usa `/logout` para revocar el acceso

🎯 **¿Listo? ¡Envía un archivo ahora!**
""",
        "start_non_premium": """¡Hola {mention}! 👋

🚀 **¡Bienvenido al bot de descargas de Telegram!**

Enlaces directos rápidos para **cualquier** archivo, ¡incluso de canales privados!

🔒 **Seguro y privado**
⚡ **Servidores rápidos**
📈 **Miles de archivos al día**

Usa los botones o **🚀 EMPEZAR** para premium.
""",
        "help": """Cómo usar el bot:

- Envía un archivo para el enlace de descarga.
- Canales privados: `/login` en el generador de sesión, luego envía la URL del post.
- `/logout` para revocar la sesión.
""",
        "about": """🤖 **Generador de enlaces de Telegram**

📦 **Versión PyroFork:** {pyro_version}
☁️ **Despliegue:** [Koyeb](https://koyeb.com)
🔗 **Repositorio:** [GitHub]({github_url})

💡 **Funciones:**
• Enlaces para cualquier archivo
• Canales privados con sesión
• Sesión cifrada
• Multi-token

⚡ **Con:** Python, Pyrogram, MongoDB
""",
        "features": """✨ **Funciones premium:**

• **Enlaces directos**: Sin restricciones del cliente
• **Canales privados**: Login seguro
• **Streaming rápido**: Vídeo en el navegador
• **Alta velocidad**
• **Sin anuncios**
""",
        "how_it_works": """🛠 **Cómo funciona:**

**1️⃣ Archivos públicos:**
Reenvía o envía un archivo — respondemos con el enlace.

**2️⃣ Canales privados:**
• `/login` para autenticarte
• Copia el enlace del mensaje
• Envíalo al bot

**3️⃣ Streaming:**
Abre el enlace para previsualizar o descargar.
""",
        "pricing": """💰 **Planes premium:**

¡Descargas directas y acceso a canales privados!

• Pases diarios/semanales/mensuales
• Pago con Crypto (USDT) o UPI
• Activación automática

Pulsa **🚀 EMPEZAR** abajo para ver precios.
""",
        "premium_required": (
            "🔒 Se requiere premium.\n\n"
            "Pulsa el botón para comprar premium."
        ),
        "btn_help": "❓ Ayuda",
        "btn_about": "ℹ️ Acerca de",
        "btn_close": "✖️ Cerrar",
        "premium_get_started": "🚀 EMPEZAR",
        "premium_how_it_works": "📖 CÓMO FUNCIONA",
        "premium_features": "💬 FUNCIONES",
        "premium_pricing": "💰 PRECIOS",
        "premium_help": "❓ AYUDA",
        "lang_saved": "Idioma actualizado.",
        "pay_choose_method": "Elige método de pago:",
        "pay_btn_crypto": "₿ USDT (BEP20)",
        "pay_btn_upi": "🇮🇳 UPI",
        "pay_method_crypto": "Cripto (USDT BEP20)",
        "pay_method_upi": "UPI",
        "pay_method_selected_header": "Método seleccionado: {method}\n\n",
        "pay_choose_duration_hint": (
            "Elige la duración.\n"
            "Pagas (precio por día × días); solo el total se redondea al alza a 2 decimales si hace falta."
        ),
        "pay_pricing_not_configured": "Precios no configurados. Contacta al propietario.",
        "pay_crypto_config_err": "Precio crypto incorrecto. Contacta al propietario.",
        "pay_upi_config_err": "Precio UPI incorrecto. Contacta al propietario.",
        "pay_failed_start": "No se pudo iniciar la compra. Inténtalo de nuevo.",
        "pay_amount_usdt": "Importe a pagar: {amount} USDT (BEP20)",
        "pay_usdt_address_block": "Dirección USDT (BSC BEP20):\n{address}",
        "pay_amount_inr": "Importe a pagar: INR {amount}",
        "pay_upi_block": "UPI ID:\n{upi_id}",
        "pay_invoice": (
            "Compra premium iniciada.\n\n"
            "Método: {method}\n"
            "Días: {days}\n"
            "{amount_line}\n\n"
            "{address_block}\n\n"
            "Tras pagar, pulsa **YA PAGUÉ**.\n"
            "Luego envía la captura de pago aquí."
        ),
        "pay_btn_i_paid": "✅ YA PAGUÉ",
        "pay_btn_cancel": "❌ CANCELAR",
        "pay_btn_confirm": "✅ CONFIRMAR",
        "pay_marked_paid_intro": (
            "Pago marcado como enviado.\n\n"
            "Sube la captura (foto o documento).\n"
            "Luego revisa los datos y pulsa CONFIRMAR.\n"
        ),
        "pay_upload_screenshot_short": "Sube la captura de pago (foto o documento).",
        "pay_step_inactive": "Paso no válido o solicitud caducada.",
        "pay_cancelled": "Compra cancelada.",
        "err_screenshot_file": "No se detectó el archivo. Envía de nuevo.",
        "err_screenshot_upload": "Falló la subida. Inténtalo de nuevo.",
        "err_unexpected_retry": "Error inesperado. Inténtalo de nuevo.",
        "pay_review_header": "Revisa los datos del pago:\n\n",
        "pay_review_txn_id": "ID transacción: {tid}",
        "pay_review_user_id": "ID usuario: {uid}",
        "pay_review_username": "Usuario: {username}",
        "pay_review_name": "Nombre: {name}",
        "pay_review_language": "Idioma: {tg_lang}",
        "pay_review_method": "Método: {method}",
        "pay_review_days": "Días: {days}",
        "pay_review_amount": "Importe: {amount}",
        "pay_submitted_wait": "Enviado al administrador. Espera confirmación.",
        "pay_fail_channel": (
            "Error al enviar al canal de transacciones. Verifica TXN_CHNL_ID y permisos del bot."
        ),
        "pay_txn_not_found": "Transacción no encontrada o caducada.",
        "pay_already_submitted": "Ya enviado. Espera la confirmación del admin.",
        "pay_txn_not_ready": "La transacción no está lista.",
        "pay_screenshot_missing": "Falta captura de pantalla.",
        "pay_days_choice": "{n} día(s)",
        "premium_approved": (
            "✅ ¡Premium aprobado!\n\n"
            "Tu acceso expira en: {expires}\n"
            "Ya puedes usar el bot."
        ),
        "premium_rejected": "❌ Pago rechazado. Puedes intentar de nuevo.",
    },
    "zh": {
        "start_premium": """你好 {mention}！👋

🚀 **欢迎使用下载链接生成机器人！**

📁 发送任意文件即可立即获得直链。

🔐 **私密内容：**
• 先使用 `/login`，再把 t.me 帖子链接发给我
• 使用 `/logout` 随时撤销访问

🎯 **准备好了就发文件吧！**
""",
        "start_non_premium": """你好 {mention}！👋

🚀 **欢迎使用 Telegram 下载机器人！**

我们为 **任意** 文件提供高速直链——包括私密频道！

🔒 **安全私密**
⚡ **全球高速节点**
📈 **每日处理大量文件**

点击下方按钮了解详情，或点 **🚀 开始** 开通会员！
""",
        "help": """使用说明：

- 发送任意文件获取下载链接。
- 私密频道：先在会话生成页 `/login`，再把帖子链接发来。
- `/logout` 可撤销会话与私密链接。
""",
        "about": """🤖 **Telegram 下载链接生成器**

📦 **PyroFork 版本：** {pyro_version}
☁️ **部署：** [Koyeb](https://koyeb.com)
🔗 **仓库：** [GitHub]({github_url})

💡 **功能：**
• 任意文件直链
• 私密频道（会话）
• 加密会话存储
• 多 Token 支持

⚡ **技术栈：** Python、Pyrogram、MongoDB
""",
        "features": """✨ **会员功能：**

• **直链下载**：绕过客户端限制
• **私密频道**：安全登录
• **高速串流**：浏览器播放
• **高速带宽**
• **无广告**
""",
        "how_it_works": """🛠 **如何使用：**

**1️⃣ 公开文件：**
转发或发送文件，机器人回复直链。

**2️⃣ 私密频道：**
• `/login` 完成验证
• 复制帖子链接
• 发给机器人

**3️⃣ 串流：**
打开链接预览或下载。
""",
        "pricing": """💰 **会员方案：**

解锁直链与私密频道访问！

• 按天/周/月灵活付费
• 支持 USDT 或 UPI
• 自动开通

点击下方 **🚀 开始** 查看价格！
""",
        "premium_required": (
            "🔒 需要会员才能使用。\n\n"
            "点击下方按钮购买会员。"
        ),
        "btn_help": "❓ 帮助",
        "btn_about": "ℹ️ 关于",
        "btn_close": "✖️ 关闭",
        "premium_get_started": "🚀 开始",
        "premium_how_it_works": "📖 使用说明",
        "premium_features": "💬 功能",
        "premium_pricing": "💰 价格",
        "premium_help": "❓ 帮助",
        "lang_saved": "语言已更新。",
        "pay_choose_method": "选择支付方式：",
        "pay_btn_crypto": "₿ USDT (BEP20)",
        "pay_btn_upi": "🇮🇳 UPI",
        "pay_method_crypto": "加密货币 (USDT BEP20)",
        "pay_method_upi": "UPI",
        "pay_method_selected_header": "已选支付方式：{method}\n\n",
        "pay_choose_duration_hint": (
            "选择订阅天数。\n"
            "费用 = 每日单价 × 天数；总额仅在需要时向上取整到 2 位小数。"
        ),
        "pay_pricing_not_configured": "未配置价格，请联系站长。",
        "pay_crypto_config_err": "加密货币价格配置有误，请联系站长。",
        "pay_upi_config_err": "UPI 价格配置有误，请联系站长。",
        "pay_failed_start": "无法开始购买，请重试。",
        "pay_amount_usdt": "应付金额：{amount} USDT (BEP20)",
        "pay_usdt_address_block": "USDT (BSC BEP20) 地址：\n{address}",
        "pay_amount_inr": "应付金额：INR {amount}",
        "pay_upi_block": "UPI ID：\n{upi_id}",
        "pay_invoice": (
            "已开始购买会员。\n\n"
            "方式：{method}\n"
            "订阅天数：{days}\n"
            "{amount_line}\n\n"
            "{address_block}\n\n"
            "付款后点击 **已付款**。\n"
            "然后将付款截图发到此对话。"
        ),
        "pay_btn_i_paid": "✅ 已付款",
        "pay_btn_cancel": "❌ 取消",
        "pay_btn_confirm": "✅ 确认",
        "pay_marked_paid_intro": (
            "已标记为已付款。\n\n"
            "请上传付款截图（图片或文件）。\n"
            "上传后核对信息并点击「确认」。\n"
        ),
        "pay_upload_screenshot_short": "请上传付款截图（图片或文件）。",
        "pay_step_inactive": "操作无效或请求已过期。",
        "pay_cancelled": "已取消购买。",
        "err_screenshot_file": "无法识别文件，请重新发送。",
        "err_screenshot_upload": "上传失败（步骤过期），请重试。",
        "err_unexpected_retry": "发生意外错误，请重试。",
        "pay_review_header": "请核对付款信息：\n\n",
        "pay_review_txn_id": "交易 ID：{tid}",
        "pay_review_user_id": "用户 ID：{uid}",
        "pay_review_username": "用户名：{username}",
        "pay_review_name": "姓名：{name}",
        "pay_review_language": "语言：{tg_lang}",
        "pay_review_method": "方式：{method}",
        "pay_review_days": "天数：{days}",
        "pay_review_amount": "金额：{amount}",
        "pay_submitted_wait": "已提交给管理员审核，请耐心等待。",
        "pay_fail_channel": "发送到交易频道失败，请检查 TXN_CHNL_ID 与机器人权限。",
        "pay_txn_not_found": "交易不存在或已过期。",
        "pay_already_submitted": "已提交，请等待管理员确认。",
        "pay_txn_not_ready": "交易暂不可提交。",
        "pay_screenshot_missing": "缺少截图。",
        "pay_days_choice": "{n} 天",
        "premium_approved": (
            "✅ 会员已通过！\n\n"
            "有效期至：{expires}\n"
            "你现在可以使用机器人。"
        ),
        "premium_rejected": "❌ 付款未通过，可重新尝试。",
    },
}
