
# Ads AI Panel – Pro (Meta + Shopify, TR) + **CAPI (v2.12)**

Sunucu-tarafı **Meta Conversions API** + Shopify **orders/paid** webhook + **fbp/fbc** ile tarayıcı sinyali birleştirme.

## Kurulum
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload
```

## ENV
- `ADMIN_PASSWORD`, `SECRET_KEY`, `BRAND_NAME`
- `SHOPIFY_STORE_URL`, `SHOPIFY_API_TOKEN`, `SHOPIFY_API_VERSION`, `SHOPIFY_WEBHOOK_SECRET` (ops.)
- `META_PIXEL_ID`, `META_ACCESS_TOKEN`, `META_TEST_EVENT_CODE`

## Shopify Webhook
- **Event:** orders/paid → URL: `/webhooks/shopify/orders_paid` (HMAC doğrulama destekli)

## CAPI Test
- `/capi/test?email=ornek@ornek.com` → Events Manager / Test Events'te görünür.

## fbp/fbc Toplama (Tarayıcı → Sunucu)
Checkout “Ekstra komut dosyaları (Additional Scripts)” alanına bu kodu ekleyin:

```html
<script>
  (function(){
    function getCookie(n){return document.cookie.split('; ').find(r=>r.startsWith(n+'='))?.split('=')[1]||''}
    var _fbp = getCookie('_fbp');
    var _fbc = getCookie('_fbc'); // meta click id varsa otomatik dolar
    // Shopify Order ID ve müşteri e-postası (Liquid değişkenleri)
    var ORDER_ID = "{{ order.id }}";
    var EMAIL = "{{ checkout.email }}";
    var VALUE = {{ checkout.total_price | divided_by: 100.0 }};
    var CURRENCY = "{{ checkout.presentment_currency }}";
    // Tarayıcı pikseli + eventID (dedup)
    if (window.fbq) {
      fbq('track','Purchase',{value:VALUE,currency:CURRENCY},{eventID:ORDER_ID});
    }
    // Server-side CAPI forward
    fetch('https://<panel-domainin>/capi/forward',{
      method:'POST',headers:{'Content-Type':'application/json'},
      body: JSON.stringify({
        event_name: 'Purchase',
        value: VALUE, currency: CURRENCY,
        email: EMAIL, phone: '',
        event_id: ORDER_ID,
        fbp: _fbp, fbc: _fbc,
        event_source_url: window.location.href,
        client_user_agent: navigator.userAgent,
        test_mode: true // canlıya geçince false
      })
    });
  })();
</script>
```

> Böylece **eventID** ile **deduplication** çalışır; tarayıcı (_Pixel_) + sunucu (CAPI) tek olaya düşer. `fbp` (first-party cookie) ve `fbc` (click id cookie) gönderildiği için eşleşme oranı güçlenir.

## Öğrenen Modül
- `/learn` → eğitim, `/optimize/suggest` → öneriler.
- Model: GradientBoostingRegressor (ROAS) + LogisticRegression (purchase olasılığı).

## Notlar
- Güvenlik için `/capi/forward` domainini sadece mağaza domaininden çağıracak şekilde (CORS, IP allowlist) sınırlandırmayı düşünebilirsiniz.
- Test modda `META_TEST_EVENT_CODE` kullanın; canlıda `test_mode:false`.
```

