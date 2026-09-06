"""Konstanta & konfigurasi default."""

DEFAULT_PASSWORD = "unud2023"
EMAIL_DOMAIN = "@student.unud.ac.id"
LOGIN_URL = "https://accounts.google.com/signin"
LOGOUT_URL = "https://accounts.google.com/Logout"
DEFAULT_SERVER_URL = "http://localhost:9377"
REQUEST_TIMEOUT = 60       # detik timeout HTTP request
WAIT_AFTER_CLICK = 5       # detik tunggu setelah klik Next
DELAY_BETWEEN_ACCOUNTS = 3  # jeda antar akun

# User agent untuk browser
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)

# Deteksi "Choose an account" / "Pilih akun"
CHOOSE_ACCOUNT_SIGNALS = [
    "choose an account", "pilih akun",
    "use another account", "gunakan akun lain",
]

# Deteksi halaman myaccount (sudah login)
MYACCOUNT_SIGNALS = [
    "myaccount.google.com", "akun google", "info pribadi",
    "keamanan & login", "sandi google", "data & privasi",
    "beranda", "favorit",
]

# Deteksi verifikasi (password sudah diganti)
VERIFY_SIGNALS = [
    "verify it\u2019s you", "verify it's you", "verifikasi",
    "open the gmail app", "google sent a notification",
    "get a verification code", "use your phone",
    "2-step", "two-step", "choose a way to verify",
    "confirm that it's you", "challenge",
    "enter a phone number", "get a text message",
    "verification code", "enter the code",
]

# Deteksi email tidak ditemukan
EMAIL_ERROR_SIGNALS = [
    "couldn't find your google account",
    "couldn\u2019t find your google account",
    "tidak ditemukan", "couldn't find", "enter a valid email",
]

# Deteksi password salah
WRONG_PWD_SIGNALS = [
    "wrong password", "incorrect password",
    "your password is incorrect", "password salah", "sandi salah",
]

# Deteksi "Something went wrong" / error Google
SOMETHING_WRONG_SIGNALS = [
    "something went wrong", "something wrong",
    "terjadi kesalahan", "coba lagi nanti",
    "unusual activity", "couldn't complete",
]

# Deteksi email ditolak Google (rejected = email tidak terdaftar/diblokir)
# URL berisi /signin/rejected atau teks ini muncul
REJECTED_URL_SIGNAL = "/signin/rejected"
REJECTED_TEXT_SIGNALS = [
    "this email address isn't associated",
    "email tidak terdaftar",
    "your email address has been blocked",
]

# Deteksi login berhasil
SUCCESS_SIGNALS = [
    "favorit", "beranda", "info pribadi", "keamanan & login",
    "sandi google", "data & privasi", "akun google",
    "welcome to your", "mentransfer konten",
]
