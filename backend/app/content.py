"""Seed content for Wilayat API.

This is sample/seed data so the API runs out-of-the-box. In production these
collections are served from PostgreSQL + Elasticsearch and sourced from
properly licensed, scholar-verified datasets.
"""

SURAHS = [
    {"n": 1, "ar": "الفاتحة", "en": "Al-Fatihah", "meaning": "The Opening", "ayat": 7, "type": "Meccan"},
    {"n": 2, "ar": "البقرة", "en": "Al-Baqarah", "meaning": "The Cow", "ayat": 286, "type": "Medinan"},
    {"n": 36, "ar": "يس", "en": "Ya-Sin", "meaning": "Ya Sin", "ayat": 83, "type": "Meccan"},
    {"n": 112, "ar": "الإخلاص", "en": "Al-Ikhlas", "meaning": "Sincerity", "ayat": 4, "type": "Meccan"},
    {"n": 114, "ar": "الناس", "en": "An-Nas", "meaning": "Mankind", "ayat": 6, "type": "Meccan"},
]

FATIHA = [
    {"n": 1, "ar": "بِسْمِ اللَّهِ الرَّحْمَٰنِ الرَّحِيمِ",
     "tr": "In the name of Allah, the Most Gracious, the Most Merciful.",
     "translit": "Bismillāhi r-raḥmāni r-raḥīm"},
    {"n": 2, "ar": "الْحَمْدُ لِلَّهِ رَبِّ الْعَالَمِينَ",
     "tr": "All praise is due to Allah, Lord of the worlds.",
     "translit": "Al-ḥamdu lillāhi rabbi l-ʿālamīn"},
    {"n": 3, "ar": "الرَّحْمَٰنِ الرَّحِيمِ", "tr": "The Most Gracious, the Most Merciful.",
     "translit": "Ar-raḥmāni r-raḥīm"},
    {"n": 4, "ar": "مَالِكِ يَوْمِ الدِّينِ", "tr": "Master of the Day of Judgment.",
     "translit": "Māliki yawmi d-dīn"},
    {"n": 5, "ar": "إِيَّاكَ نَعْبُدُ وَإِيَّاكَ نَسْتَعِينُ",
     "tr": "You alone we worship, and You alone we ask for help.",
     "translit": "Iyyāka naʿbudu wa-iyyāka nastaʿīn"},
    {"n": 6, "ar": "اهْدِنَا الصِّرَاطَ الْمُسْتَقِيمَ", "tr": "Guide us on the Straight Path.",
     "translit": "Ihdinā ṣ-ṣirāṭa l-mustaqīm"},
    {"n": 7, "ar": "صِرَاطَ الَّذِينَ أَنْعَمْتَ عَلَيْهِمْ غَيْرِ الْمَغْضُوبِ عَلَيْهِمْ وَلَا الضَّالِّينَ",
     "tr": "The path of those upon whom You have bestowed favor, not of those who earned anger nor of those who went astray.",
     "translit": "Ṣirāṭa lladhīna anʿamta ʿalayhim ghayri l-maghḍūbi ʿalayhim wa-lā ḍ-ḍāllīn"},
]

HADITH_BOOKS = [
    {"id": "kafi", "ar": "الكافي", "en": "Al-Kafi", "author": "Shaykh al-Kulayni", "count": 16199},
    {"id": "faqih", "ar": "من لا يحضره الفقيه", "en": "Man La Yahduruhu al-Faqih", "author": "Shaykh al-Saduq", "count": 5920},
    {"id": "tahdhib", "ar": "تهذيب الأحكام", "en": "Tahdhib al-Ahkam", "author": "Shaykh al-Tusi", "count": 13590},
    {"id": "istibsar", "ar": "الاستبصار", "en": "Al-Istibsar", "author": "Shaykh al-Tusi", "count": 5511},
]

HADITHS = [
    {"book": "Al-Kafi", "grade": "Sahih", "topic": "Knowledge",
     "ar": "طَلَبُ الْعِلْمِ فَرِيضَةٌ عَلَى كُلِّ مُسْلِمٍ",
     "tr": "Seeking knowledge is an obligation upon every Muslim.", "chain": "Imam al-Sadiq (AS)"},
    {"book": "Al-Kafi", "grade": "Sahih", "topic": "Intellect",
     "ar": "إِنَّمَا يُدْرَكُ الْخَيْرُ كُلُّهُ بِالْعَقْلِ",
     "tr": "All good is attained through the intellect.", "chain": "Imam al-Kazim (AS)"},
    {"book": "Man La Yahduruhu al-Faqih", "grade": "Hasan", "topic": "Worship",
     "ar": "الصَّلَاةُ عَمُودُ الدِّينِ", "tr": "Prayer is the pillar of religion.",
     "chain": "Prophet Muhammad (SAWW)"},
]

DUAS = [
    {"id": "kumayl", "ar": "دعاء كميل", "en": "Dua Kumayl", "src": "Mafatih al-Jinan", "note": "Recited on Thursday nights"},
    {"id": "tawassul", "ar": "دعاء التوسل", "en": "Dua Tawassul", "src": "Mafatih al-Jinan", "note": "Seeking intercession of the 14 Infallibles"},
    {"id": "nudba", "ar": "دعاء الندبة", "en": "Dua Nudba", "src": "Mafatih al-Jinan", "note": "Recited on Friday mornings"},
    {"id": "sahifa", "ar": "الصحيفة السجادية", "en": "Sahifa Sajjadiya", "src": "Imam al-Sajjad (AS)", "note": "The Psalms of Islam"},
]

ZIYARAT = [
    {"id": "ashura", "ar": "زيارة عاشوراء", "en": "Ziyarat Ashura", "to": "Imam al-Husayn (AS)"},
    {"id": "waritha", "ar": "زيارة وارث", "en": "Ziyarat Waritha", "to": "Imam al-Husayn (AS)"},
    {"id": "jamia", "ar": "الزيارة الجامعة الكبيرة", "en": "Ziyarat Jamia Kabira", "to": "All Imams (AS)"},
    {"id": "aminullah", "ar": "زيارة أمين الله", "en": "Ziyarat Amin Allah", "to": "The Infallibles (AS)"},
]

PRAYERS = [
    {"key": "fajr", "en": "Fajr", "ar": "الفجر", "time": "04:12"},
    {"key": "sunrise", "en": "Sunrise", "ar": "الشروق", "time": "05:48"},
    {"key": "dhuhr", "en": "Dhuhr", "ar": "الظهر", "time": "13:04"},
    {"key": "asr", "en": "Asr", "ar": "العصر", "time": "16:42"},
    {"key": "maghrib", "en": "Maghrib", "ar": "المغرب", "time": "20:18"},
    {"key": "isha", "en": "Isha", "ar": "العشاء", "time": "21:52"},
]

EVENTS = [
    {"date": "10 Muharram", "en": "Ashura — Martyrdom of Imam Husayn (AS)", "type": "shahadat"},
    {"date": "20 Safar", "en": "Arbaeen of Imam Husayn (AS)", "type": "shahadat"},
    {"date": "13 Rajab", "en": "Wiladat of Imam Ali (AS)", "type": "wiladat"},
    {"date": "15 Sha'ban", "en": "Wiladat of Imam al-Mahdi (AJ)", "type": "wiladat"},
    {"date": "18 Dhul-Hijjah", "en": "Eid al-Ghadir", "type": "wiladat"},
]

# al-Faqih is now full searchable text; keep the source PDFs as optional downloads.
_BQ = "https://babulqaim.com/wp-content/uploads/2025/03"
# edition: "ar" = Arabic-text PDF, "en" = English-translation PDF.
# These al-Faqih volumes are the Arabic edition.
PDF_BOOKS = [
    {"id": "faqih-1", "en": "Man Lā Yaḥḍuruh al-Faqīh — Vol. 1 (PDF)", "ar": "من لا يحضره الفقيه",
     "author": "Shaykh al-Ṣaduq", "cat": "Fiqh", "edition": "ar", "url": f"{_BQ}/man-la-yahduruhu-al-faqih-vol.1.pdf"},
    {"id": "faqih-2", "en": "Man Lā Yaḥḍuruh al-Faqīh — Vol. 2 (PDF)", "ar": "من لا يحضره الفقيه",
     "author": "Shaykh al-Ṣaduq", "cat": "Fiqh", "edition": "ar", "url": f"{_BQ}/man-la-yahduruhu-al-faqih-vol.2.pdf"},
    {"id": "faqih-3", "en": "Man Lā Yaḥḍuruh al-Faqīh — Vol. 3 (PDF)", "ar": "من لا يحضره الفقيه",
     "author": "Shaykh al-Ṣaduq", "cat": "Fiqh", "edition": "ar", "url": f"{_BQ}/man-la-yahduruhu-al-faqih-vol.3-1.pdf"},
    {"id": "faqih-4", "en": "Man Lā Yaḥḍuruh al-Faqīh — Vol. 4 (PDF)", "ar": "من لا يحضره الفقيه",
     "author": "Shaykh al-Ṣaduq", "cat": "Fiqh", "edition": "ar", "url": f"{_BQ}/man-la-yahduruhu-al-faqih-vol.4.pdf"},
]

MASUMEEN = [
    {"ar": "محمد ﷺ", "en": "Prophet Muhammad (SAWW)", "role": "The Seal of Prophets"},
    {"ar": "فاطمة الزهراء", "en": "Fatima al-Zahra (SA)", "role": "Leader of the women of Paradise"},
    {"ar": "علي بن أبي طالب", "en": "Imam Ali (AS)", "role": "1st Imam"},
    {"ar": "المهدي المنتظر", "en": "Imam al-Mahdi (AJ)", "role": "12th Imam — The Awaited"},
]
