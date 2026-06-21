/* Al-Wilayat — authentication frontend logic (multilingual).
   Talks to the FastAPI backend (/api/auth/*). Shares the language choice with the
   main app via localStorage("wilayat.lang"). Stores the session in
   localStorage("wilayat.auth"). */

// Same origin as the page (FastAPI serves both the site and the API), so this
// works on localhost AND on your real domain. Override with window.WILAYAT_API.
const API_BASE = (typeof window !== "undefined" && window.WILAYAT_API) || "/api";
const AUTH_KEY = "wilayat.auth";
const LANG_KEY = "wilayat.lang";

const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];

const VIEWS = ["signin", "signup", "forgot", "reset", "profile"];

// ---------------- i18n ----------------
const RTL = ["ar", "ur", "fa", "prs", "ks"];
const LANGS = [
  ["en", "English"], ["ar", "العربية"], ["ur", "اردو"], ["fa", "فارسی"],
  ["az", "Azərbaycanca"], ["ks", "کٲشُر"], ["prs", "دری فارسی"],
  ["ms", "Bahasa Melayu"], ["sg", "Singapore English"],
];
const EN = {
  tag: "Shia Islamic Library", app_name: "Al-Wilayat",
  signin_title: "Welcome back to Al-Wilayat", signin_sub: "Sign in to continue your journey of knowledge.",
  email: "Email address", password: "Password", remember: "Remember me", forgot: "Forgot password?",
  signin: "Sign In", or: "or", no_account: "Don’t have an account?", signup: "Sign Up",
  signup_title: "Create your Al-Wilayat Account", signup_sub: "Join the community in a few seconds.",
  full_name: "Full name", create_password: "Create password", confirm: "Confirm password",
  create_account: "Create Account", have_account: "Already have an account?",
  forgot_title: "Reset your password", forgot_sub: "Enter your email and we’ll send a 6-digit reset code.",
  send_code: "Send Code", back: "← Back to Sign In",
  reset_title: "Enter your reset code", reset_sub: "We emailed a 6-digit code. Enter it with your new password.",
  code: "Reset code", new_password: "New password", confirm_new: "Confirm new password", update_password: "Update Password",
  profile_title: "Your account", open_app: "Open the App", signout: "Sign Out", powered: "Powered by Aiba Dynamics",
  ph_email: "you@example.com", ph_password: "Your password", ph_create: "Create a strong password",
  ph_reenter: "Re-enter password", ph_code: "6-digit code", ph_new: "New strong password",
  ph_renew: "Re-enter new password", ph_name: "Your full name",
  m_signing: "Signing in…", m_creating: "Creating account…", m_sending: "Sending…", m_updating: "Updating…",
  m_created: "Account created! Please sign in.", m_code_sent: "If that email is registered, a reset code has been sent.",
  m_updated: "Your password has been updated. You can now sign in.", m_signedout: "You have been signed out.",
  m_welcome: "Welcome back! Redirecting…",
  e_server: "Cannot reach the server. Is the backend running on :8000?",
  e_email: "Enter a valid email address", e_pw_req: "Password is required", e_name: "Please enter your full name",
  e_weak: "Use 8+ characters with an uppercase, lowercase, number & symbol.", e_match: "Passwords do not match",
  e_code: "Enter the 6-digit code from your email", e_incorrect: "Incorrect email or password",
  e_exists: "An account with this email already exists", e_locked: "Too many attempts. Please wait a few minutes.",
  e_badcode: "This code is invalid or has expired. Please request a new one.",
  weak: "Weak", fair: "Fair", good: "Good", strong: "Strong",
};
const AUTH_I18N = { en: EN, sg: EN };
AUTH_I18N.ar = {
  tag: "مكتبة الشيعة الإسلامية", app_name: "الولاية", signin_title: "مرحباً بعودتك إلى الولاية", signin_sub: "سجّل الدخول لمواصلة رحلتك في طلب العلم.",
  email: "البريد الإلكتروني", password: "كلمة المرور", remember: "تذكّرني", forgot: "نسيت كلمة المرور؟",
  signin: "تسجيل الدخول", or: "أو", no_account: "ليس لديك حساب؟", signup: "إنشاء حساب",
  signup_title: "أنشئ حساب الولاية", signup_sub: "انضم إلى المجتمع في ثوانٍ.",
  full_name: "الاسم الكامل", create_password: "أنشئ كلمة مرور", confirm: "تأكيد كلمة المرور",
  create_account: "إنشاء الحساب", have_account: "لديك حساب بالفعل؟",
  forgot_title: "إعادة تعيين كلمة المرور", forgot_sub: "أدخل بريدك وسنرسل رمزاً من 6 أرقام.",
  send_code: "إرسال الرمز", back: "← العودة لتسجيل الدخول",
  reset_title: "أدخل رمز إعادة التعيين", reset_sub: "أرسلنا رمزاً من 6 أرقام. أدخله مع كلمة المرور الجديدة.",
  code: "رمز إعادة التعيين", new_password: "كلمة المرور الجديدة", confirm_new: "تأكيد كلمة المرور الجديدة", update_password: "تحديث كلمة المرور",
  profile_title: "حسابك", open_app: "افتح التطبيق", signout: "تسجيل الخروج", powered: "بدعم من Aiba Dynamics",
  ph_email: "you@example.com", ph_password: "كلمة المرور", ph_create: "أنشئ كلمة مرور قوية",
  ph_reenter: "أعد إدخال كلمة المرور", ph_code: "رمز من 6 أرقام", ph_new: "كلمة مرور جديدة قوية",
  ph_renew: "أعد إدخال كلمة المرور الجديدة", ph_name: "اسمك الكامل",
  m_signing: "جارٍ تسجيل الدخول…", m_creating: "جارٍ إنشاء الحساب…", m_sending: "جارٍ الإرسال…", m_updating: "جارٍ التحديث…",
  m_created: "تم إنشاء الحساب! سجّل الدخول.", m_code_sent: "إذا كان البريد مسجّلاً، فقد أُرسل رمز.",
  m_updated: "تم تحديث كلمة المرور. يمكنك تسجيل الدخول الآن.", m_signedout: "تم تسجيل خروجك.",
  m_welcome: "مرحباً بعودتك! جارٍ التحويل…",
  e_server: "تعذّر الوصول للخادم. هل الخادم يعمل على :8000؟",
  e_email: "أدخل بريداً إلكترونياً صحيحاً", e_pw_req: "كلمة المرور مطلوبة", e_name: "أدخل اسمك الكامل",
  e_weak: "استخدم 8 أحرف على الأقل مع حرف كبير وصغير ورقم ورمز.", e_match: "كلمتا المرور غير متطابقتين",
  e_code: "أدخل الرمز المكوّن من 6 أرقام", e_incorrect: "البريد أو كلمة المرور غير صحيحة",
  e_exists: "يوجد حساب بهذا البريد بالفعل", e_locked: "محاولات كثيرة. انتظر بضع دقائق.",
  e_badcode: "هذا الرمز غير صالح أو منتهٍ. اطلب رمزاً جديداً.",
  weak: "ضعيفة", fair: "مقبولة", good: "جيدة", strong: "قوية",
};
AUTH_I18N.ur = {
  tag: "شیعہ اسلامی لائبریری", app_name: "ولایت", signin_title: "ولایت میں خوش آمدید", signin_sub: "علم کے سفر کو جاری رکھنے کے لیے سائن اِن کریں۔",
  email: "ای میل", password: "پاس ورڈ", remember: "مجھے یاد رکھیں", forgot: "پاس ورڈ بھول گئے؟",
  signin: "سائن اِن", or: "یا", no_account: "اکاؤنٹ نہیں ہے؟", signup: "سائن اَپ",
  signup_title: "اپنا ولایت اکاؤنٹ بنائیں", signup_sub: "چند سیکنڈ میں شامل ہوں۔",
  full_name: "پورا نام", create_password: "پاس ورڈ بنائیں", confirm: "پاس ورڈ کی تصدیق",
  create_account: "اکاؤنٹ بنائیں", have_account: "پہلے سے اکاؤنٹ ہے؟",
  forgot_title: "پاس ورڈ ری سیٹ کریں", forgot_sub: "اپنا ای میل درج کریں، ہم 6 ہندسوں کا کوڈ بھیجیں گے۔",
  send_code: "کوڈ بھیجیں", back: "← سائن اِن پر واپس",
  reset_title: "ری سیٹ کوڈ درج کریں", reset_sub: "ہم نے 6 ہندسوں کا کوڈ بھیجا۔ نئے پاس ورڈ کے ساتھ درج کریں۔",
  code: "ری سیٹ کوڈ", new_password: "نیا پاس ورڈ", confirm_new: "نئے پاس ورڈ کی تصدیق", update_password: "پاس ورڈ اپ ڈیٹ کریں",
  profile_title: "آپ کا اکاؤنٹ", open_app: "ایپ کھولیں", signout: "سائن آؤٹ", powered: "Aiba Dynamics کے زیرِ اہتمام",
  ph_email: "you@example.com", ph_password: "آپ کا پاس ورڈ", ph_create: "مضبوط پاس ورڈ بنائیں",
  ph_reenter: "پاس ورڈ دوبارہ درج کریں", ph_code: "6 ہندسوں کا کوڈ", ph_new: "نیا مضبوط پاس ورڈ",
  ph_renew: "نیا پاس ورڈ دوبارہ درج کریں", ph_name: "آپ کا پورا نام",
  m_signing: "سائن اِن ہو رہا ہے…", m_creating: "اکاؤنٹ بن رہا ہے…", m_sending: "بھیجا جا رہا ہے…", m_updating: "اپ ڈیٹ ہو رہا ہے…",
  m_created: "اکاؤنٹ بن گیا! سائن اِن کریں۔", m_code_sent: "اگر ای میل رجسٹرڈ ہے تو کوڈ بھیج دیا گیا۔",
  m_updated: "پاس ورڈ اپ ڈیٹ ہو گیا۔ اب سائن اِن کریں۔", m_signedout: "آپ سائن آؤٹ ہو گئے۔",
  m_welcome: "خوش آمدید! منتقل کیا جا رہا ہے…",
  e_server: "سرور تک رسائی نہیں۔ کیا بیک اینڈ :8000 پر چل رہا ہے؟",
  e_email: "درست ای میل درج کریں", e_pw_req: "پاس ورڈ ضروری ہے", e_name: "اپنا پورا نام درج کریں",
  e_weak: "کم از کم 8 حروف، بڑے چھوٹے حرف، عدد اور علامت۔", e_match: "پاس ورڈ مماثل نہیں",
  e_code: "ای میل سے 6 ہندسوں کا کوڈ درج کریں", e_incorrect: "ای میل یا پاس ورڈ غلط",
  e_exists: "اس ای میل سے اکاؤنٹ پہلے سے موجود ہے", e_locked: "بہت زیادہ کوششیں۔ چند منٹ انتظار کریں۔",
  e_badcode: "یہ کوڈ غلط یا ختم ہو چکا ہے۔ نیا کوڈ منگوائیں۔",
  weak: "کمزور", fair: "مناسب", good: "اچھا", strong: "مضبوط",
};
AUTH_I18N.fa = {
  tag: "کتابخانه اسلامی شیعه", app_name: "ولایت", signin_title: "به ولایت خوش آمدید", signin_sub: "برای ادامه مسیر دانش وارد شوید.",
  email: "ایمیل", password: "گذرواژه", remember: "مرا به خاطر بسپار", forgot: "گذرواژه را فراموش کرده‌اید؟",
  signin: "ورود", or: "یا", no_account: "حساب ندارید؟", signup: "ثبت‌نام",
  signup_title: "حساب ولایت خود را بسازید", signup_sub: "در چند ثانیه عضو شوید.",
  full_name: "نام کامل", create_password: "ساخت گذرواژه", confirm: "تأیید گذرواژه",
  create_account: "ساخت حساب", have_account: "قبلاً حساب دارید؟",
  forgot_title: "بازنشانی گذرواژه", forgot_sub: "ایمیل خود را وارد کنید تا کد ۶ رقمی بفرستیم.",
  send_code: "ارسال کد", back: "← بازگشت به ورود",
  reset_title: "کد بازنشانی را وارد کنید", reset_sub: "کد ۶ رقمی فرستادیم. آن را با گذرواژه جدید وارد کنید.",
  code: "کد بازنشانی", new_password: "گذرواژه جدید", confirm_new: "تأیید گذرواژه جدید", update_password: "به‌روزرسانی گذرواژه",
  profile_title: "حساب شما", open_app: "باز کردن برنامه", signout: "خروج", powered: "با پشتیبانی Aiba Dynamics",
  ph_email: "you@example.com", ph_password: "گذرواژه شما", ph_create: "یک گذرواژه قوی بسازید",
  ph_reenter: "گذرواژه را دوباره وارد کنید", ph_code: "کد ۶ رقمی", ph_new: "گذرواژه جدید قوی",
  ph_renew: "گذرواژه جدید را دوباره وارد کنید", ph_name: "نام کامل شما",
  m_signing: "در حال ورود…", m_creating: "در حال ساخت حساب…", m_sending: "در حال ارسال…", m_updating: "در حال به‌روزرسانی…",
  m_created: "حساب ساخته شد! وارد شوید.", m_code_sent: "اگر ایمیل ثبت شده باشد، کد ارسال شد.",
  m_updated: "گذرواژه به‌روزرسانی شد. اکنون وارد شوید.", m_signedout: "خارج شدید.",
  m_welcome: "خوش آمدید! در حال انتقال…",
  e_server: "اتصال به سرور ممکن نشد. آیا سرور روی :8000 اجراست؟",
  e_email: "ایمیل معتبر وارد کنید", e_pw_req: "گذرواژه لازم است", e_name: "نام کامل خود را وارد کنید",
  e_weak: "حداقل ۸ نویسه با حروف بزرگ، کوچک، عدد و نماد.", e_match: "گذرواژه‌ها مطابقت ندارند",
  e_code: "کد ۶ رقمی ایمیل را وارد کنید", e_incorrect: "ایمیل یا گذرواژه نادرست",
  e_exists: "حسابی با این ایمیل وجود دارد", e_locked: "تلاش‌های زیاد. چند دقیقه صبر کنید.",
  e_badcode: "این کد نامعتبر یا منقضی است. کد جدید بخواهید.",
  weak: "ضعیف", fair: "متوسط", good: "خوب", strong: "قوی",
};
AUTH_I18N.prs = AUTH_I18N.fa;   // Dari ≈ Persian
AUTH_I18N.ks = AUTH_I18N.ur;    // Kashmiri reads Urdu-style script
AUTH_I18N.az = {
  tag: "Şiə İslam Kitabxanası", app_name: "Vilayət", signin_title: "Vilayətə xoş gəlmisiniz", signin_sub: "Bilik yolunuza davam etmək üçün daxil olun.",
  email: "E-poçt", password: "Şifrə", remember: "Məni xatırla", forgot: "Şifrəni unutmusunuz?",
  signin: "Daxil ol", or: "və ya", no_account: "Hesabınız yoxdur?", signup: "Qeydiyyat",
  signup_title: "Vilayət hesabınızı yaradın", signup_sub: "Bir neçə saniyəyə qoşulun.",
  full_name: "Tam ad", create_password: "Şifrə yaradın", confirm: "Şifrəni təsdiqləyin",
  create_account: "Hesab yarat", have_account: "Artıq hesabınız var?",
  forgot_title: "Şifrəni sıfırlayın", forgot_sub: "E-poçtunuzu daxil edin, 6 rəqəmli kod göndərəcəyik.",
  send_code: "Kod göndər", back: "← Girişə qayıt",
  reset_title: "Sıfırlama kodunu daxil edin", reset_sub: "6 rəqəmli kod göndərdik. Yeni şifrə ilə daxil edin.",
  code: "Sıfırlama kodu", new_password: "Yeni şifrə", confirm_new: "Yeni şifrəni təsdiqləyin", update_password: "Şifrəni yenilə",
  profile_title: "Hesabınız", open_app: "Tətbiqi aç", signout: "Çıxış", powered: "Aiba Dynamics tərəfindən dəstəklənir",
  ph_email: "you@example.com", ph_password: "Şifrəniz", ph_create: "Güclü şifrə yaradın",
  ph_reenter: "Şifrəni təkrar daxil edin", ph_code: "6 rəqəmli kod", ph_new: "Yeni güclü şifrə",
  ph_renew: "Yeni şifrəni təkrar daxil edin", ph_name: "Tam adınız",
  m_signing: "Daxil olunur…", m_creating: "Hesab yaradılır…", m_sending: "Göndərilir…", m_updating: "Yenilənir…",
  m_created: "Hesab yaradıldı! Daxil olun.", m_code_sent: "E-poçt qeydiyyatdadırsa, kod göndərildi.",
  m_updated: "Şifrə yeniləndi. İndi daxil ola bilərsiniz.", m_signedout: "Çıxış etdiniz.",
  m_welcome: "Xoş gəlmisiniz! Yönləndirilir…",
  e_server: "Serverə çatmaq olmur. Backend :8000-də işləyir?",
  e_email: "Düzgün e-poçt daxil edin", e_pw_req: "Şifrə tələb olunur", e_name: "Tam adınızı daxil edin",
  e_weak: "Ən azı 8 simvol: böyük, kiçik hərf, rəqəm və simvol.", e_match: "Şifrələr uyğun gəlmir",
  e_code: "E-poçtdakı 6 rəqəmli kodu daxil edin", e_incorrect: "E-poçt və ya şifrə yanlışdır",
  e_exists: "Bu e-poçtla hesab artıq mövcuddur", e_locked: "Çox cəhd. Bir neçə dəqiqə gözləyin.",
  e_badcode: "Bu kod yanlış və ya vaxtı keçib. Yeni kod istəyin.",
  weak: "Zəif", fair: "Orta", good: "Yaxşı", strong: "Güclü",
};
AUTH_I18N.ms = {
  tag: "Perpustakaan Islam Syiah", app_name: "Al-Wilayah", signin_title: "Selamat kembali ke Al-Wilayah", signin_sub: "Log masuk untuk meneruskan perjalanan ilmu anda.",
  email: "Alamat e-mel", password: "Kata laluan", remember: "Ingat saya", forgot: "Lupa kata laluan?",
  signin: "Log Masuk", or: "atau", no_account: "Tiada akaun?", signup: "Daftar",
  signup_title: "Cipta Akaun Al-Wilayah anda", signup_sub: "Sertai komuniti dalam beberapa saat.",
  full_name: "Nama penuh", create_password: "Cipta kata laluan", confirm: "Sahkan kata laluan",
  create_account: "Cipta Akaun", have_account: "Sudah ada akaun?",
  forgot_title: "Set semula kata laluan", forgot_sub: "Masukkan e-mel anda, kami akan hantar kod 6 digit.",
  send_code: "Hantar Kod", back: "← Kembali ke Log Masuk",
  reset_title: "Masukkan kod set semula", reset_sub: "Kami e-mel kod 6 digit. Masukkan dengan kata laluan baharu.",
  code: "Kod set semula", new_password: "Kata laluan baharu", confirm_new: "Sahkan kata laluan baharu", update_password: "Kemas kini Kata Laluan",
  profile_title: "Akaun anda", open_app: "Buka Aplikasi", signout: "Log Keluar", powered: "Dikuasakan oleh Aiba Dynamics",
  ph_email: "you@example.com", ph_password: "Kata laluan anda", ph_create: "Cipta kata laluan kuat",
  ph_reenter: "Masukkan semula kata laluan", ph_code: "Kod 6 digit", ph_new: "Kata laluan baharu yang kuat",
  ph_renew: "Masukkan semula kata laluan baharu", ph_name: "Nama penuh anda",
  m_signing: "Sedang log masuk…", m_creating: "Mencipta akaun…", m_sending: "Menghantar…", m_updating: "Mengemas kini…",
  m_created: "Akaun dicipta! Sila log masuk.", m_code_sent: "Jika e-mel didaftarkan, kod telah dihantar.",
  m_updated: "Kata laluan dikemas kini. Anda boleh log masuk.", m_signedout: "Anda telah log keluar.",
  m_welcome: "Selamat kembali! Mengalihkan…",
  e_server: "Tidak dapat menghubungi pelayan. Backend berjalan di :8000?",
  e_email: "Masukkan e-mel yang sah", e_pw_req: "Kata laluan diperlukan", e_name: "Masukkan nama penuh anda",
  e_weak: "Guna 8+ aksara: huruf besar, kecil, nombor & simbol.", e_match: "Kata laluan tidak sepadan",
  e_code: "Masukkan kod 6 digit dari e-mel", e_incorrect: "E-mel atau kata laluan salah",
  e_exists: "Akaun dengan e-mel ini sudah wujud", e_locked: "Terlalu banyak cubaan. Tunggu beberapa minit.",
  e_badcode: "Kod ini tidak sah atau tamat tempoh. Minta kod baharu.",
  weak: "Lemah", fair: "Sederhana", good: "Baik", strong: "Kuat",
};

// The login page stays in English (it does not change the app language).
let LANG = "en";
const T = (k) => (AUTH_I18N[LANG] && AUTH_I18N[LANG][k]) || EN[k] || k;

function applyAuthLang(lang) {
  if (!AUTH_I18N[lang]) lang = "en";
  LANG = lang;
  document.documentElement.lang = lang;
  document.documentElement.dir = RTL.includes(lang) ? "rtl" : "ltr";
  $$("[data-i18n]").forEach((n) => (n.textContent = T(n.dataset.i18n)));
  $$("[data-i18n-ph]").forEach((n) => (n.placeholder = T(n.dataset.i18nPh)));
  const cur = $("#authLangLabel");
  if (cur) cur.textContent = (LANGS.find((l) => l[0] === lang) || [])[1] || "";
  refreshStrengthLabels();
}

// ---------------- session helpers ----------------
const saveSession = (data) => localStorage.setItem(AUTH_KEY, JSON.stringify({ token: data.access_token, user: data.user }));
const getSession = () => { try { return JSON.parse(localStorage.getItem(AUTH_KEY) || "null"); } catch { return null; } };
const clearSession = () => localStorage.removeItem(AUTH_KEY);

// ---------------- validation ----------------
const EMAIL_RE = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;
const passwordWeak = (pw) => (pw || "").length < 8 || !/[A-Z]/.test(pw) || !/[a-z]/.test(pw) || !/\d/.test(pw) || !/[^A-Za-z0-9]/.test(pw);
function passwordScore(pw) {
  let s = 0;
  if ((pw || "").length >= 8) s++;
  if (/[A-Z]/.test(pw) && /[a-z]/.test(pw)) s++;
  if (/\d/.test(pw)) s++;
  if (/[^A-Za-z0-9]/.test(pw)) s++;
  return s;
}

// ---------------- UI helpers ----------------
function showView(name) {
  VIEWS.forEach((v) => { const n = $("#view-" + v); if (n) n.hidden = v !== name; });
  hideBanner();
  if (name !== "reset" && location.hash.slice(1) !== name && VIEWS.includes(name)) history.replaceState(null, "", "#" + name);
}
function banner(msg, kind = "info") { const b = $("#banner"); b.textContent = msg; b.className = "banner " + kind; b.hidden = false; }
function hideBanner() { $("#banner").hidden = true; }
function fieldError(input, msg) {
  const field = input.closest(".field");
  const err = field && field.querySelector("[data-err]");
  if (field) field.classList.toggle("invalid", !!msg);
  if (err) err.textContent = msg || "";
  return !msg;
}
function clearErrors(form) {
  $$(".field", form).forEach((f) => f.classList.remove("invalid"));
  $$("[data-err]", form).forEach((e) => (e.textContent = ""));
}
async function postJSON(path, body) {
  return fetch(API_BASE + path, { method: "POST", headers: { "Content-Type": "application/json", Accept: "application/json" }, body: JSON.stringify(body) });
}
// Localized message for a backend error response (by status).
async function errMsg(res) {
  if (res.status === 401) return T("e_incorrect");
  if (res.status === 409) return T("e_exists");
  if (res.status === 429) return T("e_locked");
  if (res.status === 422) return T("e_weak");
  if (res.status === 400) return T("e_badcode");
  try { const d = await res.json(); if (typeof d.detail === "string") return d.detail; } catch { /* ignore */ }
  return T("e_server");
}
function withLoading(btn, label, fn) {
  const original = btn.textContent;
  btn.disabled = true; btn.textContent = label;
  return fn().finally(() => { btn.disabled = false; btn.textContent = original; });
}

// ============================================================ SIGN IN =====
$("#view-signin").addEventListener("submit", async (e) => {
  e.preventDefault();
  const form = e.currentTarget; clearErrors(form); hideBanner();
  const email = form.email.value.trim(), password = form.password.value;
  let ok = true;
  if (!EMAIL_RE.test(email)) ok = fieldError(form.email, T("e_email")) && ok;
  if (!password) ok = fieldError(form.password, T("e_pw_req")) && ok;
  if (!ok) return;
  await withLoading(form.querySelector(".btn-primary"), T("m_signing"), async () => {
    try {
      const res = await postJSON("/auth/login", { email, password, remember: form.remember.checked });
      if (!res.ok) return banner(await errMsg(res), "error");
      saveSession(await res.json());
      banner(T("m_welcome"), "success");
      setTimeout(() => (location.href = "index.html"), 700);
    } catch { banner(T("e_server"), "error"); }
  });
});

// ============================================================ SIGN UP =====
$("#view-signup").addEventListener("submit", async (e) => {
  e.preventDefault();
  const form = e.currentTarget; clearErrors(form); hideBanner();
  const full_name = form.full_name.value.trim(), email = form.email.value.trim();
  const password = form.password.value, confirm = form.confirm.value;
  let ok = true;
  if (full_name.length < 2) ok = fieldError(form.full_name, T("e_name")) && ok;
  if (!EMAIL_RE.test(email)) ok = fieldError(form.email, T("e_email")) && ok;
  if (passwordWeak(password)) ok = fieldError(form.password, T("e_weak")) && ok;
  if (password !== confirm) ok = fieldError(form.confirm, T("e_match")) && ok;
  if (!ok) return;
  await withLoading(form.querySelector(".btn-primary"), T("m_creating"), async () => {
    try {
      const res = await postJSON("/auth/register", { full_name, email, password });
      if (!res.ok) return banner(await errMsg(res), "error");
      form.reset();
      showView("signin");
      const si = $("#view-signin"); si.email.value = email; si.password.focus();
      banner(T("m_created"), "success");
    } catch { banner(T("e_server"), "error"); }
  });
});

// ============================================================ FORGOT =======
$("#view-forgot").addEventListener("submit", async (e) => {
  e.preventDefault();
  const form = e.currentTarget; clearErrors(form); hideBanner();
  const email = form.email.value.trim();
  if (!EMAIL_RE.test(email)) return fieldError(form.email, T("e_email"));
  await withLoading(form.querySelector(".btn-primary"), T("m_sending"), async () => {
    try {
      await postJSON("/auth/forgot-password", { email });
      showView("reset");
      const r = $("#view-reset"); r.email.value = email; r.code.focus();
      banner(T("m_code_sent"), "success");
    } catch { banner(T("e_server"), "error"); }
  });
});

// ============================================================ RESET ========
$("#view-reset").addEventListener("submit", async (e) => {
  e.preventDefault();
  const form = e.currentTarget; clearErrors(form); hideBanner();
  const email = form.email.value.trim(), code = form.code.value.trim();
  const password = form.password.value, confirm = form.confirm.value;
  let ok = true;
  if (!EMAIL_RE.test(email)) ok = fieldError(form.email, T("e_email")) && ok;
  if (!/^\d{4,8}$/.test(code)) ok = fieldError(form.code, T("e_code")) && ok;
  if (passwordWeak(password)) ok = fieldError(form.password, T("e_weak")) && ok;
  if (password !== confirm) ok = fieldError(form.confirm, T("e_match")) && ok;
  if (!ok) return;
  await withLoading(form.querySelector(".btn-primary"), T("m_updating"), async () => {
    try {
      const res = await postJSON("/auth/reset-password", { email, code, password });
      if (!res.ok) return banner(await errMsg(res), "error");
      banner(T("m_updated"), "success");
      setTimeout(() => showView("signin"), 1200);
    } catch { banner(T("e_server"), "error"); }
  });
});

// ============================================================ PROFILE ======
$("#logoutBtn").addEventListener("click", () => { clearSession(); banner(T("m_signedout"), "info"); showView("signin"); });
function renderProfile(user) {
  $("#profileAvatar").textContent = (user.full_name || "?").trim().charAt(0).toUpperCase();
  $("#profileName").textContent = user.full_name;
  $("#profileEmail").textContent = user.email;
  $("#profileRole").textContent = user.role;
  showView("profile");
}

// ---------------- show / hide password (SVG eye / eye-off) ----------------
const SVG_ATTRS = 'viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"';
const EYE_ICON = `<svg ${SVG_ATTRS}><path d="M2 12s3-7 10-7 10 7 10 7-3 7-10 7-10-7-10-7Z"/><circle cx="12" cy="12" r="3"/></svg>`;
const EYE_OFF_ICON = `<svg ${SVG_ATTRS}><path d="M9.88 9.88a3 3 0 1 0 4.24 4.24"/><path d="M10.73 5.08A10.43 10.43 0 0 1 12 5c7 0 10 7 10 7a13.16 13.16 0 0 1-1.67 2.68"/><path d="M6.61 6.61A13.526 13.526 0 0 0 2 12s3 7 10 7a9.74 9.74 0 0 0 5.39-1.61"/><line x1="2" x2="22" y1="2" y2="22"/></svg>`;
$$("[data-toggle]").forEach((btn) =>
  btn.addEventListener("click", () => {
    const input = btn.parentElement.querySelector("input");
    const show = input.type === "password";
    input.type = show ? "text" : "password";
    btn.innerHTML = show ? EYE_OFF_ICON : EYE_ICON;
  })
);

// ---------------- live password strength ----------------
function refreshStrengthLabels() {
  $$('input[name="password"]').forEach((input) => {
    const meter = input.closest(".field")?.querySelector("[data-strength]");
    if (meter && !meter.hidden) {
      const words = ["", T("weak"), T("fair"), T("good"), T("strong")];
      meter.querySelector(".strength-label").textContent = words[+meter.dataset.level || 0] || "";
    }
  });
}
$$('input[name="password"]').forEach((input) => {
  const meter = input.closest(".field")?.querySelector("[data-strength]");
  if (!meter) return;
  const label = meter.querySelector(".strength-label");
  input.addEventListener("input", () => {
    const v = input.value;
    meter.hidden = !v;
    const score = passwordScore(v);
    meter.dataset.level = String(score);
    label.textContent = ["", T("weak"), T("fair"), T("good"), T("strong")][score] || "";
  });
});

// ---------------- in-card navigation links ----------------
$$("[data-nav]").forEach((a) => a.addEventListener("click", (e) => { e.preventDefault(); showView(a.dataset.nav); }));

// ---------------- boot ----------------
function boot() {
  applyAuthLang(LANG);
  const session = getSession();
  if (session?.user) { renderProfile(session.user); return; }
  const hash = location.hash.slice(1);
  showView(VIEWS.includes(hash) && hash !== "reset" && hash !== "profile" ? hash : "signin");
}
window.addEventListener("hashchange", () => {
  const hash = location.hash.slice(1);
  if (VIEWS.includes(hash) && hash !== "reset" && hash !== "profile") showView(hash);
});
boot();
