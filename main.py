# app.py
# تشغيل: pip install flask requests
# ثم: python app.py

from flask import Flask, render_template_string, request, session
import requests

app = Flask(__name__)
app.secret_key = 'solana-checker-secret-key-2024'

API_KEY = "6e5dbf89-00c8-4676-85d7-023ec051a65a"
MIN_SOL = 0.03
PAGE_LIMIT = 100

def fetch_page(address, cursor=None):
    url = f"https://api.helius.xyz/v0/addresses/{address}/transactions?api-key={API_KEY}&limit={PAGE_LIMIT}"
    if cursor:
        url += f"&cursor={cursor}"
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    return r.json()

def collect_recipients(address):
    recipients = set()
    cursor = None
    while True:
        data = fetch_page(address, cursor)
        if not isinstance(data, list) or len(data) == 0:
            break
        for tx in data:
            for t in tx.get("nativeTransfers", []):
                amount = int(t.get("amount", 0)) / 1e9
                to_addr = t.get("toUserAccount") or t.get("toUser") or t.get("to")
                # تجاهل العنوان المدخل نفسه
                if to_addr and amount >= MIN_SOL and to_addr != address:
                    recipients.add(to_addr)
        # التحقق من وجود المزيد من البيانات
        if len(data) == PAGE_LIMIT:
            # استخدام signature آخر معاملة كـ cursor للصفحة التالية
            if data and 'signature' in data[-1]:
                cursor = data[-1]['signature']
            else:
                break
        else:
            # إذا كان أقل من حد الصفحة، فهذه آخر صفحة
            break
    return list(recipients)

def collect_senders(address):
    senders = set()
    cursor = None
    while True:
        data = fetch_page(address, cursor)
        if not isinstance(data, list) or len(data) == 0:
            break
        for tx in data:
            for t in tx.get("nativeTransfers", []):
                amount = int(t.get("amount", 0)) / 1e9
                from_addr = t.get("fromUserAccount") or t.get("fromUser") or t.get("from")
                # تجاهل العنوان المدخل نفسه
                if from_addr and amount >= MIN_SOL and from_addr != address:
                    senders.add(from_addr)
        # التحقق من وجود المزيد من البيانات
        if len(data) == PAGE_LIMIT:
            # استخدام signature آخر معاملة كـ cursor للصفحة التالية
            if data and 'signature' in data[-1]:
                cursor = data[-1]['signature']
            else:
                break
        else:
            # إذا كان أقل من حد الصفحة، فهذه آخر صفحة
            break
    return list(senders)

def clean_solana_address(address):
    """تنظيف عنوان سولانا من المسافات والرموز المخفية"""
    if not address:
        return address
    address = address.strip()
    hidden_chars = ['\u200b', '\u200c', '\u200d', '\ufeff', '\u00a0']
    for char in hidden_chars:
        address = address.replace(char, '')
    address = ''.join(address.split())
    address = address.strip('"\'')
    return address

def validate_solana_address(address):
    """التحقق من صحة عنوان سولانا"""
    if len(address) < 32 or len(address) > 44:
        return False
    base58_chars = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
    for char in address:
        if char not in base58_chars:
            return False
    return True

def get_sol_balance(address):
    """جلب رصيد SOL لعنوان محدد"""
    try:
        url = f"https://api.helius.xyz/v0/addresses/{address}/balances?api-key={API_KEY}"
        r = requests.get(url, timeout=5)
        r.raise_for_status()
        data = r.json()
        native_balance = data.get('nativeBalance', 0)
        return round(float(native_balance) / 1e9, 3)
    except:
        return 0.0

def get_rent_info(address):
    """حساب إجمالي الـ rent القابل للاسترداد من التوكنات"""
    try:
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "getTokenAccountsByOwner",
            "params": [
                address,
                {"programId": "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"},
                {"encoding": "jsonParsed"}
            ]
        }
        r = requests.post("https://solana-mainnet.g.alchemy.com/v2/L6FPdLCpDpxb79Hm2mfysZJUzlpOQ7Mq", 
                         json=payload, timeout=10)
        r.raise_for_status()
        data = r.json()
        
        if 'result' in data and 'value' in data['result']:
            token_count = len(data['result']['value'])
            # كل token account يتطلب حوالي 0.00203928 SOL كـ rent
            total_rent = token_count * 0.00203928
            return round(total_rent, 3)
        return 0.0
    except:
        return 0.0

def get_balances_batch(addresses):
    """جلب أرصدة عدة عناوين في دفعة واحدة"""
    balances = {}
    for addr in addresses:
        balances[addr] = get_sol_balance(addr)
    return balances

class AddressData:
    """فئة لتمثيل بيانات العنوان مع الرصيد والـ rent"""
    def __init__(self, address, balance, rent=0.0):
        self.address = address
        self.balance = balance
        self.rent = rent

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
  <meta charset="UTF-8">
  <title>فاحص عناوين سولانا</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <style>
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: #1a1a1a; color: #fff; min-height: 100vh; padding: 20px; }
    .container { background: #2d2d2d; padding: 30px; border-radius: 15px; box-shadow: 0 10px 30px rgba(0,0,0,0.5); max-width: 1200px; margin: 0 auto; }
    h1 { color: #4CAF50; margin-bottom: 30px; font-size: 28px; font-weight: 300; text-align: center; }
    .input-section { background: #333; padding: 25px; border-radius: 10px; margin-bottom: 30px; }
    .input-group { margin-bottom: 20px; position: relative; }
    input[type="text"] { width: 100%; padding: 15px; background: #404040; border: 2px solid #555; border-radius: 8px; color: #fff; font-size: 16px; outline: none; transition: all 0.3s ease; }
    input[type="text"]:focus { border-color: #4CAF50; background: #4a4a4a; }
    input[type="text"]::placeholder { color: #aaa; }
    .buttons-container { display: flex; gap: 15px; flex-wrap: wrap; }
    .check-btn { background: #4CAF50; color: white; padding: 15px 40px; border: none; border-radius: 8px; font-size: 18px; font-weight: 500; cursor: pointer; transition: all 0.3s ease; flex: 1; min-width: 200px; }
    .check-btn:hover { background: #45a049; transform: translateY(-2px); box-shadow: 0 5px 15px rgba(76,175,80,0.3); }
    .check-btn:active { transform: translateY(0); }
    .check-btn.withdrawal { background: #2196F3; }
    .check-btn.withdrawal:hover { background: #1976D2; box-shadow: 0 5px 15px rgba(33,150,243,0.3); }
    .results { margin-top: 25px; }
    .error { color: #f44336; background: #2d1515; padding: 15px; border-radius: 8px; border-left: 4px solid #f44336; margin-bottom: 20px; }
    .success { color: #4CAF50; background: #1a2d1a; padding: 15px; border-radius: 8px; border-left: 4px solid #4CAF50; margin-bottom: 20px; }
    .success.withdrawal { color: #2196F3; background: #151d2d; border-left: 4px solid #2196F3; }
    .results-section { margin-bottom: 30px; }
    table { width: 100%; border-collapse: collapse; margin-top: 20px; background: #333; border-radius: 8px; overflow: hidden; }
    td, th { border: 1px solid #555; padding: 12px; font-size: 14px; word-break: break-all; }
    th { background: #404040; color: #4CAF50; font-weight: 600; }
    td { background: #2a2a2a; }
    .duplicate { box-shadow: 0 0 10px 2px rgba(255, 0, 0, 0.5) !important; background: #3d2a2a !important; }
    .copy-btn { background: #4CAF50; color: white; padding: 6px 12px; border: none; border-radius: 4px; cursor: pointer; font-size: 12px; transition: all 0.3s ease; }
    .copy-btn:hover { background: #45a049; transform: scale(1.05); }
    .section-title { color: #4CAF50; font-size: 20px; margin-bottom: 15px; padding-bottom: 10px; border-bottom: 2px solid #4CAF50; }
    .section-title.withdrawal { color: #2196F3; border-bottom: 2px solid #2196F3; }
    .loading { display: none; text-align: center; padding: 20px; color: #4CAF50; }
    .spinner { border: 3px solid #333; border-top: 3px solid #4CAF50; border-radius: 50%; width: 40px; height: 40px; animation: spin 1s linear infinite; margin: 0 auto 15px; }
    @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
  </style>
</head>
<body>
  <div class="container">
    <h1>فاحص عناوين سولانا</h1>
    <div class="input-section">
      <form method="post" id="checkForm">
        <div class="input-group">
          <input type="text" id="addressInput" name="address" placeholder="أدخل عنوان سولانا للفحص" required value="{{ current_address or '' }}">
        </div>
      </form>
    </div>

    <div class="loading" id="loadingDiv">
      <div class="spinner"></div>
      <div>جاري البحث...</div>
    </div>

    {% if error %}
    <div class="error">
      {{ error }}
    </div>
    {% endif %}

    {% if deposits %}
    <div class="results-section">
      <h2 class="section-title withdrawal">💸 عناوين السحب (سحب من العنوان المفحوص)</h2>
      <div class="success withdrawal">
        ✅ تم العثور على {{ deposits|length }} عنوان
      </div>

      <table>
        <tr>
          <th>العنوان</th>
          <th>رصيد SOL</th>
          <th>Rent</th>
          <th>نسخ</th>
        </tr>
        {% for addr_data in deposits %}
        <tr>
          <td><span class="address-display">{{ addr_data.address[:4] }}...{{ addr_data.address[-4:] }}</span></td>
          <td>{{ "%.3f"|format(addr_data.balance) }}</td>
          <td>{{ "%.3f"|format(addr_data.rent) }}</td>
          <td><button class="copy-btn" onclick="copyText('{{ addr_data.address }}')">📋</button></td>
        </tr>
        {% endfor %}
      </table>
    </div>
    {% endif %}

    {% if withdrawals %}
    <div class="results-section">
      <h2 class="section-title">💰 عناوين الايداع (إيداع في العنوان المفحوص)</h2>
      <div class="success">
        ✅ تم العثور على {{ withdrawals|length }} عنوان
      </div>

      <table>
        <tr>
          <th>العنوان</th>
          <th>رصيد SOL</th>
          <th>Rent</th>
          <th>نسخ</th>
        </tr>
        {% for addr_data in withdrawals %}
        <tr>
          <td><span class="address-display">{{ addr_data.address[:4] }}...{{ addr_data.address[-4:] }}</span></td>
          <td>{{ "%.3f"|format(addr_data.balance) }}</td>
          <td>{{ "%.3f"|format(addr_data.rent) }}</td>
          <td><button class="copy-btn" onclick="copyText('{{ addr_data.address }}')">📋</button></td>
        </tr>
        {% endfor %}
      </table>
    </div>
    {% endif %}
  </div>

  <script>
    // فحص تلقائي عند لصق العنوان فقط
    document.getElementById('addressInput').addEventListener('paste', function(e) {
      setTimeout(function() {
        const address = document.getElementById('addressInput').value.trim();
        document.getElementById('addressInput').blur();
        if (address && address.length >= 32) {
          document.getElementById('loadingDiv').style.display = 'block';
          document.getElementById('checkForm').submit();
        }
      }, 200); // انتظار 200ms للتأكد من اكتمال عملية اللصق
    });
    
    // وظائف لعرض العناوين بشكل مختصر
    function abbreviateAddress(addr) {
      if (addr.length <= 8) return addr;
      return addr.substring(0, 4) + '...' + addr.substring(addr.length - 4);
    }

    function copyText(text) {
      navigator.clipboard.writeText(text).then(() => {
        alert("تم نسخ العنوان:\\n" + text);
      }).catch(() => {
        const textArea = document.createElement('textarea');
        textArea.value = text;
        document.body.appendChild(textArea);
        textArea.select();
        document.execCommand('copy');
        document.body.removeChild(textArea);
        alert("تم نسخ العنوان:\\n" + text);
      });
    }
  </script>
</body>
</html>
"""

@app.route("/", methods=["GET", "POST"])
def index():
    
    # تحويل بيانات الجلسة إلى كائنات AddressData
    deposits_data = session.get('deposits', None)
    withdrawals_data = session.get('withdrawals', None)
    
    deposits = None
    withdrawals = None
    
    if deposits_data:
        try:
            # إذا كانت البيانات في تنسيق tuples (عنوان, رصيد, rent)
            deposits = [AddressData(addr, balance, rent) for addr, balance, rent in deposits_data]
        except (ValueError, TypeError):
            try:
                # إذا كانت البيانات في تنسيق tuples (عنوان, رصيد)
                deposits = [AddressData(addr, balance, 0.0) for addr, balance in deposits_data]
            except (ValueError, TypeError):
                # إذا كانت البيانات في تنسيق قديم (قائمة عناوين فقط)
                deposits = [AddressData(addr, 0.0, 0.0) for addr in deposits_data]
    
    if withdrawals_data:
        try:
            # إذا كانت البيانات في تنسيق tuples (عنوان, رصيد, rent)
            withdrawals = [AddressData(addr, balance, rent) for addr, balance, rent in withdrawals_data]
        except (ValueError, TypeError):
            try:
                # إذا كانت البيانات في تنسيق tuples (عنوان, رصيد)
                withdrawals = [AddressData(addr, balance, 0.0) for addr, balance in withdrawals_data]
            except (ValueError, TypeError):
                # إذا كانت البيانات في تنسيق قديم (قائمة عناوين فقط)
                withdrawals = [AddressData(addr, 0.0, 0.0) for addr in withdrawals_data]
    
    error = None
    current_address = session.get('current_address', None)

    if request.method == "POST":
        address = request.form.get("address", "").strip()

        if address:
            address = clean_solana_address(address)
            
            # إذا كان العنوان مختلف عن المحفوظ، امسح النتائج السابقة
            if current_address != address:
                session.pop('deposits', None)
                session.pop('withdrawals', None)
                deposits = None
                withdrawals = None
            
            current_address = address
            session['current_address'] = current_address

            if not validate_solana_address(address):
                error = "❌ عنوان سولانا غير صحيح - تحقق من التنسيق"
            else:
                try:
                    # فحص الايداع والسحب معاً
                    deposits_addrs = collect_recipients(address)
                    withdrawals_addrs = collect_senders(address)
                    
                    # جلب أرصدة العناوين ومعلومات الـ rent
                    all_addresses = list(set(deposits_addrs + withdrawals_addrs))
                    balances = get_balances_batch(all_addresses)
                    
                    # جلب معلومات الـ rent لجميع العناوين
                    rent_info = {}
                    for addr in all_addresses:
                        rent_info[addr] = get_rent_info(addr)
                    
                    # تحويل العناوين إلى وحدات بيانات مع معلومات الـ rent
                    deposits = [AddressData(addr, balances.get(addr, 0.0), rent_info.get(addr, 0.0)) for addr in deposits_addrs]
                    withdrawals = [AddressData(addr, balances.get(addr, 0.0), rent_info.get(addr, 0.0)) for addr in withdrawals_addrs]
                    
                    session['deposits'] = [(d.address, d.balance, d.rent) for d in deposits]
                    session['withdrawals'] = [(w.address, w.balance, w.rent) for w in withdrawals]
                    
                    if not deposits and not withdrawals:
                        error = "⚠️ لم يتم العثور على أي معاملات لهذا العنوان"
                except Exception as e:
                    error = f"❌ خطأ في جمع البيانات: {str(e)}"
        else:
            error = "❌ يرجى إدخال عنوان سولانا"

    return render_template_string(HTML_TEMPLATE, 
                                  deposits=deposits,
                                  withdrawals=withdrawals, 
                                  error=error,
                                  current_address=current_address,
                                  min_sol=MIN_SOL)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)