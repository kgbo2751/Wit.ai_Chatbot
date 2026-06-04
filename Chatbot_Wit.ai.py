from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from dotenv import load_dotenv
from firebase_admin import credentials, firestore
import firebase_admin
import os
import requests
import random

app = Flask(__name__)
app.secret_key = os.urandom(24)

load_dotenv("Wit.ai_Key.env")
WIT_ACCESS_TOKEN = os.getenv("WIT_ACCESS_TOKEN")
LIBRETRANSLATE_URL = "https://libretranslate.de/translate"

translate_cache = {}

cred = credentials.Certificate("firebase_key.json")
firebase_admin.initialize_app(cred)
db = firestore.client()

def translate_text(text, source_lang, target_lang):
    if source_lang == target_lang:
        return text
    cache_key = f"{source_lang}->{target_lang}:{text}"
    if cache_key in translate_cache:
        return translate_cache[cache_key]
    try:
        payload = {"q": text, "source": source_lang, "target": target_lang, "format": "text"}
        response = requests.post(LIBRETRANSLATE_URL, json=payload, timeout=5)
        response.raise_for_status()
        translated = response.json().get("translatedText", text)
        translate_cache[cache_key] = translated
        return translated
    except Exception as e:
        print("Translate Error:", e)
        return text

def wit_ai(message):
    lower_msg = message.lower()
    if lower_msg in ["목록", "list"]:
        return {"intents": [{"name": "List", "confidence": 1}], "text": message}
    if not WIT_ACCESS_TOKEN:
        return {"Error": "Wit.ai Token Error"}
    url = f"https://api.wit.ai/message?v=20220330&q={message}"
    headers = {"Authorization": f"Bearer {WIT_ACCESS_TOKEN}"}
    try:
        response = requests.get(url, headers=headers, timeout=5)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        return {"error": f"API Request Error: {str(e)}"}

def contains_hangul(text):
    return any('\uac00' <= c <= '\ud7a3' for c in text)

def contains_english(text):
    return any(c.isascii() and c.isalpha() for c in text)

def save_question(user_message, lang):
    col_name = "questions_ko" if lang=="ko" else "questions_en"
    doc_ref = db.collection(col_name).document(user_message)
    doc = doc_ref.get()
    if doc.exists:
        doc_ref.update({
            "count": firestore.Increment(1),
            "last_time": firestore.SERVER_TIMESTAMP
        })
    else:
        doc_ref.set({
            "text": user_message,
            "count": 1,
            "last_time": firestore.SERVER_TIMESTAMP
        })

def get_top5_questions(lang):
    col_name = "questions_ko" if lang=="ko" else "questions_en"
    docs = db.collection(col_name)\
             .order_by("count", direction=firestore.Query.DESCENDING)\
             .limit(5).stream()
    result = []
    for doc in docs:
        count = doc.to_dict().get("count", 0)
        if lang == "ko":
            result.append(f"{doc.to_dict()['text']} ({count}회)")
        else:
            result.append(f"{doc.to_dict()['text']} ({count} times)")
    return result

size_list = ["S", "M", "L", "XL"]
fabric_list_ko = ["코튼", "린넨", "나일론", "폴리에스테르"]
fabric_list_en = ["Cotton", "Linen", "Nylon", "Polyester"]
color_list_ko = ["네이비", "차콜", "카키", "블랙"]
color_list_en = ["Navy", "Charcoal", "Khaki", "Black"]
delivery_list_ko = ["CJ대한통운", "롯데택배", "로젠택배"]
delivery_list_en = ["CJ Logistics", "Lotte Courier", "Logen"]

def answers(response):
    lang = session.get("lang", "ko")
    intents = response.get("intents", [])
    text = response.get("text", "")
    if not intents or intents[0].get("confidence", 0) < 0.3:
        return "🤔 죄송해요, 이해하지 못했어요." if lang=="ko" else "🤔 Sorry, I didn't understand."
    intent = intents[0].get("name", "")
    if lang == "en" and not intent.endswith("_EN"):
        intent += "_EN"
    elif lang == "ko" and intent.endswith("_EN"):
        intent = intent.replace("_EN", "")
    if intent == "List":
        return (
            "질문 목록들<br>"
            "1. 상품 📦️ - 사이즈, 소재, 색상, 재입고 예정일, 상품 추천<br>"
            "2. 배송 🚚 - 배송 예정일, 택배사<br>"
            "3. 교환/환불/반품 🔄 - 교환/환불/반품 방법 및 예정일<br>"
            "4. 주문 🛒 - 주문 현황<br>"
            "5. 이벤트 🎉 - 지금 진행중인 이벤트<br>"
            "6. 기타 ☎️ - 상담원 연결, 상담 가능 시간"
        )
    if intent == "List_EN":
        return (
            "Question List<br>"
            "1. Product 📦️ - Size, Fabric, Color, Restock Date, Product Recommendation<br>"
            "2. Delivery 🚚 - Estimated Delivery Date, Courier<br>"
            "3. Exchange/Refund/Return 🔄 - Methods and Expected Dates<br>"
            "4. Order 🛒 - Order Status<br>"
            "5. Event 🎉 - Ongoing Events<br>"
            "6. Others ☎️ - Connect to Agent, Service Hours"
        )
    if intent == "Suggest":
        entities = response.get("entities", {})
        product_entities = entities.get("product_type:product_type", [])
        if product_entities:
            product_type = product_entities[0].get("value", "").lower()
            if product_type == "운동화":
                return (
                    "운동화를 추천해 드리겠습니다.<br>"
                    "<div class='recommend'>"
                        "<div class='recommend_item'><img src='/static/newbalance_530.png'><div class='recommend_name'>뉴발란스 530</div></div>"
                        "<div class='recommend_item'><img src='/static/nike_airforce1.png'><div class='recommend_name'>나이키 에어포스1</div></div>"
                        "<div class='recommend_item'><img src='/static/converse_chuck.png'><div class='recommend_name'>컨버스 척70</div></div>"
                    "</div>"
                )
            elif product_type == "아우터":
                return (
                    "아우터를 추천해 드리겠습니다.<br>"
                    "<div class='recommend'>"
                        "<div class='recommend_item'><img src='/static/northface_wind.png'><div class='recommend_name'>노스페이스 바람막이</div></div>"
                        "<div class='recommend_item'><img src='/static/adidas_track.png'><div class='recommend_name'>아디다스 트랙탑</div></div>"
                        "<div class='recommend_item'><img src='/static/alpha_ma1.png'><div class='recommend_name'>알파 MA-1</div></div>"
                    "</div>"
                )
            elif product_type == "바지":
                return (
                    "바지를 추천해 드리겠습니다.<br>"
                    "<div class='recommend'>"
                        "<div class='recommend_item'><img src='/static/levis_denim.png'><div class='recommend_name'>리바이스 데님팬츠</div></div>"
                        "<div class='recommend_item'><img src='/static/musinsa_cargo.png'><div class='recommend_name'>무신사 카고팬츠</div></div>"
                        "<div class='recommend_item'><img src='/static/uniqlo_slacks.png'><div class='recommend_name'>유니클로 슬랙스</div></div>"
                    "</div>"
                )
    if intent == "Suggest_EN":
        entities = response.get("entities", {})
        product_entities = entities.get("product_type_en:product_type_en", [])
        if product_entities:
            product_type = product_entities[0].get("value", "").lower()
            if product_type == "sneakers":
                return (
                    "Here are some sneaker recommendations.<br>"
                    "<div class='recommend'>"
                        "<div class='recommend_item'><img src='/static/newbalance_530.png'><div class='recommend_name'>New Balance 530</div></div>"
                        "<div class='recommend_item'><img src='/static/nike_airforce1.png'><div class='recommend_name'>Nike Airforce 1</div></div>"
                        "<div class='recommend_item'><img src='/static/converse_chuck.png'><div class='recommend_name'>Converse Chuck 70</div></div>"
                    "</div>"
                )
            elif product_type == "outerwear":
                return (
                    "Here are some outerwear recommendations.<br>"
                    "<div class='recommend'>"
                        "<div class='recommend_item'><img src='/static/northface_wind.png'><div class='recommend_name'>The North Face Windbreaker</div></div>"
                        "<div class='recommend_item'><img src='/static/adidas_track.png'><div class='recommend_name'>Adidas Track Top</div></div>"
                        "<div class='recommend_item'><img src='/static/alpha_ma1.png'><div class='recommend_name'>Alpha MA-1</div></div>"
                    "</div>"
                )
            elif product_type == "pants":
                return (
                    "Here are some pants recommendations.<br>"
                    "<div class='recommend'>"
                        "<div class='recommend_item'><img src='/static/levis_denim.png'><div class='recommend_name'>Levi's Denim Pants</div></div>"
                        "<div class='recommend_item'><img src='/static/musinsa_cargo.png'><div class='recommend_name'>Musinsa Cargo Pants</div></div>"
                        "<div class='recommend_item'><img src='/static/uniqlo_slacks.png'><div class='recommend_name'>Uniqlo Slacks</div></div>"
                    "</div>"
                )
    if intent == "Event":
        entities = response.get("entities", {})
        event_entities = entities.get("event_type:event_type", [])
        if event_entities:
            event_type = event_entities[0].get("value", "").lower()
            if event_type == "출석 이벤트":
                return "출석 이벤트 📅 매일 출석마다 포인트 적립<br><div class='event_img'><img src='/static/event_attend.png'></div>"
            elif event_type == "친구 초대 이벤트":
                return "친구 초대 이벤트 🧑‍🤝‍🧑 친구 초대마다 포인트 적립<br><div class='event_img'><img src='/static/event_invite.png'></div>"
            elif event_type == "포인트 적립 이벤트":
                return "포인트 적립 이벤트 💳️ 결제 금액의 0.01% 포인트로 적립<br><div class='event_img'><img src='/static/event_purchase.png'></div>"
    if intent == "Event_EN":
        entities = response.get("entities", {})
        event_entities = entities.get("event_type_en:event_type_en", [])
        if event_entities:
            event_type = event_entities[0].get("value", "").lower()
            if event_type == "attendance event":
                return "Attendance Event 📅 Earn points daily.<br><div class='event_img'><img src='/static/event_attend.png'></div>"
            elif event_type == "friend invite event":
                return "Friend invite event 🧑‍🤝‍🧑 Earn points for each friend invited.<br><div class='event_img'><img src='/static/event_invite.png'></div>"
            elif event_type == "point accumulation event":
                return "Point accumulation event 💳️ Earn 0.01% points from purchase amount.<br><div class='event_img'><img src='/static/event_purchase.png'></div>"
    if intent == "Agent":
        html = (
            "<p>상담원을 연결하겠습니다. 실시간 채팅은 하단 버튼을 눌러 시작하실 수 있습니다.</p>"
            "<div class='agent_box'>"
                "<div class='agent_section1'>"
                    "<img src='/static/agent.png' class='agent_img'>"
                    "<div class='agent_name'>John</div>"
                "</div>"
                "<div class='agent_section2'>"
                    "<div class='agent_text'>고객 지원 상담원</div>"
                    "<button class='agent_chat'>채팅 시작</button>"
                "</div>"
            "</div>"
        )
        return html
    if intent == "Agent_EN":
        html = (
            "<p>Connecting you to an agent. You can start live chat by clicking the button below.</p>"
            "<div class='agent_box'>"
                "<div class='agent_section1'>"
                    "<img src='/static/agent.png' class='agent_img'>"
                    "<div class='agent_name'>John</div>"
                "</div>"
                "<div class='agent_section2'>"
                    "<div class='agent_text'>Customer Support Agent</div>"
                    "<button class='agent_chat'>Start</button>"
                "</div>"
            "</div>"
        )
        return html
    answers_dict = {
        "Hello": "👋 안녕하세요! Helpbot이에요, 무엇을 도와드릴까요?",
        "Hello_EN": "👋 Hello! How can I help you?",
        "Thanks": "👏 더욱더 노력하는 Helpbot이 되겠습니다.",
        "Thanks_EN": "👏 Thank you! Helpbot will try harder.",
        "Size": f"상품의 사이즈는 {random.choice(size_list)}입니다.",
        "Size_EN": f"The product size is {random.choice(size_list)}.",
        "Fabric": f"상품의 소재는 {random.choice(fabric_list_ko)}입니다.",
        "Fabric_EN": f"The product material is {random.choice(fabric_list_en)}.",
        "Color": f"상품의 색상은 {random.choice(color_list_ko)}입니다.",
        "Color_EN": f"The product color is {random.choice(color_list_en)}.",
        "Restock": f"재입고 예정일은 {random.randint(1,31)}일 입니다.",
        "Restock_EN": f"The restock date is in {random.randint(1,31)} days.",
        "Suggest_Question": "상품 추천 목록으로는 운동화, 아우터, 바지가 있습니다.",
        "Suggest_Question_EN": "Recommended products are sneakers, outerwear, and pants.",
        "Delivery": f"배송 예정일은 {random.randint(1,31)}일 입니다.",
        "Delivery_EN": f"The estimated delivery date is in {random.randint(1,31)} days.",
        "Company": f"택배사는 {random.choice(delivery_list_ko)}입니다.",
        "Company_EN": f"The courier company is {random.choice(delivery_list_en)}.",
        "Exchange": "교환/환불/반품은 마이페이지-상품에서 하실 수 있습니다.",
        "Exchange_EN": "You can exchange/refund/return the product in My Page - Products.",
        "ExchangeDay": f"교환/환불/반품 예정일은 {random.randint(1,31)}일 입니다.",
        "ExchangeDay_EN": f"The expected exchange/refund/return date is in {random.randint(1,31)} days.",
        "Order": f"주문 현황은 {random.choice(['결제완료','상품준비중','배송출발','배송완료'])}입니다.",
        "Order_EN": f"The order status is {random.choice(['Payment Completed','Preparing Product','Shipped','Delivered'])}.",
        "Event_Question": f"현재 진행 중인 이벤트는 {random.choice(['출석 이벤트','친구 초대 이벤트','결제시 포인트 적립'])}입니다.",
        "Event_Question_EN": f"The current events are {random.choice(['Attendance Event','Friend Invitation Event','Purchase Points Accumulation'])}.",
        "AgentTime": "상담 가능 시간은 오전 09시~오후 18시입니다.",
        "AgentTime_EN": "The customer support is available from 09:00 to 18:00.",
    }
    return answers_dict.get(intent, "🤔 죄송해요, 이해하지 못했어요." if lang=="ko" else "🤔 Sorry, I didn't understand.")

@app.route("/")
def index():
    lang = session.get("lang", "ko")
    return render_template("Chatbot_Wit.ai_Web.html", lang=lang)

@app.route("/chat", methods=["POST"])
def chat():
    user_message = request.json.get("message", "").strip()
    if user_message.lower() in ["자주 질문한 내용", "frequently asked questions", "faq", "top5"]:
        lang = session.get("lang","ko")
        top_messages = get_top5_questions(lang)
        number_emojis = ["1️⃣","2️⃣","3️⃣","4️⃣","5️⃣"]
        if not top_messages:
            return jsonify({"answer":"아직 저장된 대화가 없습니다." if lang=="ko" else "No saved conversations yet."})
        top_messages = [f"{number_emojis[i]} {top_messages[i]}" for i in range(len(top_messages))]
        title = "🔥 가장 많이 입력된 내용 Top 5 🔥" if lang=="ko" else "🔥 Most Frequently Asked Questions Top 5 🔥"
        return jsonify({"answer": title + "<br>" + "<br>".join(top_messages)})

    if contains_hangul(user_message):
        detected_lang = "ko"
        target_lang = "en"
    elif contains_english(user_message):
        detected_lang = "en"
        target_lang = "ko"
    else:
        detected_lang = session.get("lang","ko")
        target_lang = detected_lang

    response = wit_ai(user_message)
    answer = answers(response)
    save_question(user_message, detected_lang)
    if detected_lang != target_lang:
        answer = translate_text(answer, detected_lang, target_lang)
    return jsonify({"answer": answer})

@app.route("/set_language/<lang>")
def set_language(lang):
    if lang not in ["ko","en"]:
        lang="ko"
    session["lang"]=lang
    return redirect(url_for("index"))

if __name__=="__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)