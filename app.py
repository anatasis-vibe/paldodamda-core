"""
PaldoDamdA OS — 도매처 가격검색 v2
5초 안에 검색 → 최저가 확인 → 주문처 결정

Run:
    streamlit run app.py
"""
import json
import sqlite3
import sys
import tempfile
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT    = Path(__file__).parent
DB_PATH = ROOT / "data" / "paldodamda.db"
sys.path.insert(0, str(ROOT))

# ─── 페이지 설정 ────────────────────────────────────────────────────
st.set_page_config(
    page_title="PaldoDamdA OS",
    page_icon="🌾",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown("""
<style>
  .block-container { padding-top: 1rem; max-width: 1200px; }

  .best-card {
    background: linear-gradient(135deg, #166534, #15803d);
    color: white; border-radius: 14px;
    padding: 1.4rem 1.8rem; margin-bottom: 1.2rem;
    box-shadow: 0 4px 12px rgba(0,0,0,.15);
  }
  .best-card .bc-label { font-size: .8rem; opacity: .8; letter-spacing: .05em; margin-bottom: .3rem; }
  .best-card .bc-price { font-size: 2.2rem; font-weight: 700; margin: 0; line-height: 1.1; }
  .best-card .bc-sub   { font-size: .9rem; opacity: .85; margin-top: .35rem; }
  .best-card .bc-bdg   { margin-top: .6rem; display: flex; gap: .5rem; flex-wrap: wrap; }
  .bc-b  { background: rgba(255,255,255,.18); border-radius: 20px; padding: 3px 10px; font-size: .78rem; }
  .bc-bg { background: rgba(134,239,172,.25); border-radius: 20px; padding: 3px 10px; font-size: .78rem; }
  .bc-bo { background: rgba(251,191,36,.25);  border-radius: 20px; padding: 3px 10px; font-size: .78rem; }

  .recent-lbl { font-size: .78rem; color: #6b7280; margin-bottom: .3rem; }

  div[data-testid="stButton"] > button {
    border-radius: 10px; border: 1px solid #e5e7eb;
    text-align: left; height: auto; padding: .7rem 1rem;
    line-height: 1.4; white-space: pre-wrap;
  }
  div[data-testid="stButton"] > button:hover {
    border-color: #16a34a; background: #f0fdf4;
  }
  [data-testid="stTabs"] button { font-size: .95rem; }
</style>
""", unsafe_allow_html=True)


# ─── DB 헬퍼 ────────────────────────────────────────────────────────

@st.cache_resource
def get_conn():
    c = sqlite3.connect(DB_PATH, check_same_thread=False)
    c.row_factory = sqlite3.Row
    return c


def qry(sql, params=()):
    return [dict(r) for r in get_conn().execute(sql, params).fetchall()]


def run_sql(sql, params=()):
    c = get_conn()
    c.execute(sql, params)
    c.commit()


# ─── 세션 초기화 ────────────────────────────────────────────────────

if "search_history" not in st.session_state:
    st.session_state["search_history"] = []
if "selected_product" not in st.session_state:
    st.session_state["selected_product"] = None


def push_history(term):
    h = st.session_state["search_history"]
    if term in h:
        h.remove(term)
    h.insert(0, term)
    st.session_state["search_history"] = h[:8]


# ─── 헤더 + 탭 ─────────────────────────────────────────────────────

st.markdown("## 🌾 PaldoDamdA OS")

tab_search, tab_review, tab_import, tab_history = st.tabs([
    "🔍 상품 검색",
    "✅ 검수 필요",
    "📥 가격표 업데이트",
    "📜 업데이트 이력",
])


# ═══════════════════════════════════════════════════════════════════
# TAB 1 — 상품 검색 + 가격 비교
# ═══════════════════════════════════════════════════════════════════

with tab_search:

    # 검색창
    sc1, sc2 = st.columns([6, 1])
    with sc1:
        q_input = st.text_input(
            "검색어",
            placeholder="참외  /  신비복숭아  /  초당옥수수  /  전복",
            label_visibility="collapsed",
        )
    with sc2:
        search_btn = st.button("검색", type="primary", use_container_width=True)

    # 최근 검색어
    if st.session_state["search_history"]:
        st.markdown('<p class="recent-lbl">최근 검색</p>', unsafe_allow_html=True)
        h_list = st.session_state["search_history"]
        h_cols = st.columns(min(len(h_list), 8))
        for i, h in enumerate(h_list):
            with h_cols[i]:
                if st.button(h, key="hist_" + str(i), use_container_width=True):
                    st.session_state["hist_click"] = h
                    st.rerun()

    # 최근 검색어 클릭 처리
    q_text = st.session_state.pop("hist_click", None)
    if not q_text and (q_input or search_btn):
        q_text = q_input

    # 검색 실행
    if q_text:
        push_history(q_text)
        like = "%" + q_text + "%"

        products = qry(
            "SELECT sp.id, sp.standard_name, sp.category, "
            "COUNT(po.id) AS cnt, MIN(po.price) AS lo, MAX(po.price) AS hi "
            "FROM standard_products sp "
            "LEFT JOIN product_offers po "
            "ON po.standard_product_id = sp.id AND po.needs_review=0 AND po.price>0 "
            "WHERE sp.standard_name LIKE ? "
            "OR sp.id IN (SELECT standard_product_id FROM product_aliases WHERE alias LIKE ?) "
            "GROUP BY sp.id ORDER BY cnt DESC, sp.standard_name",
            [like, like],
        )

        if not products:
            st.info("검색 결과가 없습니다.")
        else:
            st.caption(str(len(products)) + "개 상품")
            n_cols = min(len(products), 4)
            cols   = st.columns(n_cols)
            for i, p in enumerate(products):
                price_str = (
                    "₩{:,}  ~  ₩{:,}".format(p["lo"], p["hi"])
                    if p["lo"] else "가격 없음"
                )
                label = "{}\n\n{} | {}개 도매처\n\n{}".format(
                    p["standard_name"], p["category"] or "", p["cnt"], price_str,
                )
                with cols[i % n_cols]:
                    if st.button(label, key="p_" + str(p["id"]), use_container_width=True):
                        st.session_state["selected_product"] = p

    # 가격 비교
    if st.session_state["selected_product"]:
        p = st.session_state["selected_product"]
        st.divider()

        hdr1, hdr2 = st.columns([8, 1])
        with hdr1:
            st.markdown("### " + p["standard_name"])
        with hdr2:
            if st.button("✕ 닫기"):
                st.session_state["selected_product"] = None
                st.rerun()

        offers = qry(
            "SELECT s.name AS sup, po.price, "
            "ri.raw_product_name AS orig, ri.raw_option AS opt, "
            "po.weight_value AS wv, po.weight_unit AS wu, "
            "po.quantity_value AS cv, po.quantity_unit AS cu, "
            "po.quality_grade AS grade, po.cultivation_type AS cult, "
            "po.package_type AS pkg, po.attributes AS tag, po.status AS st, "
            "po.jeju_available AS jeju, po.jeju_extra_fee AS jeju_fee, "
            "po.island_available AS island, po.island_extra_fee AS island_fee, "
            "sf.received_date AS fdate "
            "FROM product_offers po "
            "JOIN suppliers s ON s.id = po.supplier_id "
            "LEFT JOIN raw_items ri ON ri.id = po.raw_item_id "
            "LEFT JOIN source_files sf ON sf.id = ri.source_file_id "
            "WHERE po.standard_product_id = ? "
            "AND po.needs_review = 0 AND po.price IS NOT NULL AND po.price > 0 "
            "ORDER BY po.price ASC",
            [p["id"]],
        )

        if not offers:
            st.info("가격 데이터가 없습니다.")
        else:
            # Best Buy 카드
            best  = offers[0]
            w_str = "{}{}".format(best["wv"], best["wu"]) if best["wv"] else ""
            c_str = "{}{}".format(best["cv"], best["cu"]) if best["cv"] else ""
            spec  = " · ".join(x for x in [w_str, c_str, best["grade"]] if x)

            bdg = ""
            if best["jeju"] and best["jeju"] != "N":
                fee = "₩{:,}".format(best["jeju_fee"]) if best["jeju_fee"] else "무료"
                bdg += '<span class="bc-bg">🏝 제주 ' + fee + '</span>'
            if best["island"] and best["island"] != "N":
                fee = "₩{:,}".format(best["island_fee"]) if best["island_fee"] else "무료"
                bdg += '<span class="bc-bo">⛵ 도서 ' + fee + '</span>'
            if best["st"]:
                bdg += '<span class="bc-b">📦 ' + str(best["st"]) + '</span>'
            if not bdg:
                bdg = '<span class="bc-b">배송 정보 없음</span>'

            st.markdown(
                '<div class="best-card">'
                '<div class="bc-label">🥇 추천 구매</div>'
                '<div class="bc-price">₩{price:,}</div>'
                '<div class="bc-sub">{sup}{spec}</div>'
                '<div class="bc-bdg">{bdg}</div>'
                '</div>'.format(
                    price=best["price"],
                    sup=best["sup"] + ("  ·  " if spec else ""),
                    spec=spec,
                    bdg=bdg,
                ),
                unsafe_allow_html=True,
            )

            # 가격 비교 테이블
            detail_on = st.toggle("상세 보기", value=False)
            st.caption("{}개 도매처 가격 비교".format(len(offers)))

            rows = []
            for rank, o in enumerate(offers, 1):
                w = "{}{}".format(o["wv"], o["wu"]) if o["wv"] else ""
                c = "{}{}".format(o["cv"], o["cu"]) if o["cv"] else ""
                j_disp = ""
                if o["jeju"] and o["jeju"] != "N":
                    j_disp = "O" if not o["jeju_fee"] else "₩{:,}".format(o["jeju_fee"])
                i_disp = ""
                if o["island"] and o["island"] != "N":
                    i_disp = "O" if not o["island_fee"] else "₩{:,}".format(o["island_fee"])
                ship = " / ".join(x for x in [j_disp, i_disp] if x) or "-"

                row = {
                    "#":      rank,
                    "도매처": o["sup"],
                    "공급가": "₩{:,}".format(o["price"]),
                    "출하":   o["st"] or "-",
                    "배송":   ship,
                }
                if detail_on:
                    row["원본상품명"] = o["orig"] or ""
                    row["중량"]     = w
                    row["입수"]     = c
                    row["등급"]     = o["grade"] or ""
                    row["재배"]     = o["cult"] or ""
                    row["태그"]     = o["tag"] or ""
                    row["파일날짜"] = o["fdate"] or ""
                rows.append(row)

            df = pd.DataFrame(rows)
            st.dataframe(df, use_container_width=True, hide_index=True,
                         column_config={
                             "#":      st.column_config.NumberColumn(width="small"),
                             "공급가": st.column_config.TextColumn(width="medium"),
                         })

            with st.expander("📥 CSV 다운로드"):
                csv = df.to_csv(index=False, encoding="utf-8-sig")
                st.download_button("CSV 저장", data=csv,
                                   file_name="{}_가격비교.csv".format(p["standard_name"]),
                                   mime="text/csv")

            # 상품 상세
            with st.expander("상품 상세 정보"):
                aliases = qry(
                    "SELECT alias FROM product_aliases WHERE standard_product_id=?", [p["id"]]
                )
                last_upd = qry(
                    "SELECT MAX(sf.received_date) AS d "
                    "FROM product_offers po "
                    "LEFT JOIN raw_items ri ON ri.id=po.raw_item_id "
                    "LEFT JOIN source_files sf ON sf.id=ri.source_file_id "
                    "WHERE po.standard_product_id=?",
                    [p["id"]],
                )
                prices  = [o["price"] for o in offers]
                avg_p   = int(sum(prices) / len(prices)) if prices else 0

                d1, d2 = st.columns(2)
                with d1:
                    st.write("**표준상품명:** " + p["standard_name"])
                    st.write("**카테고리:** " + (p["category"] or "-"))
                    alias_str = ", ".join(r["alias"] for r in aliases) if aliases else "-"
                    st.write("**Alias:** " + alias_str)
                with d2:
                    st.write("**도매처 수:** {}개".format(len(offers)))
                    st.write("**최저가:** ₩{:,}".format(min(prices)) if prices else "-")
                    st.write("**최고가:** ₩{:,}".format(max(prices)) if prices else "-")
                    st.write("**평균가:** ₩{:,}".format(avg_p) if avg_p else "-")
                    d = last_upd[0]["d"] if last_upd else None
                    st.write("**최근 업데이트:** " + (d or "-"))


# ═══════════════════════════════════════════════════════════════════
# TAB 2 — 검수 필요
# ═══════════════════════════════════════════════════════════════════

with tab_review:
    st.subheader("검수 필요")

    n_pending  = qry("SELECT COUNT(*) AS n FROM review_queue WHERE status='pending'")[0]["n"]
    n_approved = qry("SELECT COUNT(*) AS n FROM review_queue WHERE status='approved'")[0]["n"]
    n_sp       = qry("SELECT COUNT(*) AS n FROM standard_products")[0]["n"]

    m1, m2, m3 = st.columns(3)
    m1.metric("검수 대기", "{:,}건".format(n_pending))
    m2.metric("승인 완료", "{:,}건".format(n_approved))
    m3.metric("표준 상품", "{}개".format(n_sp))

    st.divider()

    if n_pending == 0:
        st.success("검수할 항목이 없습니다. 🎉")
    else:
        sp_list = qry(
            "SELECT id, standard_name, category FROM standard_products "
            "ORDER BY category, standard_name"
        )
        sp_map  = {"{} ({})".format(r["standard_name"], r["category"]): r["id"] for r in sp_list}
        sp_keys = list(sp_map.keys())

        sup_names = ["전체"] + sorted({
            r["supplier_name"] for r in qry(
                "SELECT DISTINCT supplier_name FROM review_queue "
                "WHERE status='pending' AND supplier_name IS NOT NULL"
            )
        })
        sup_filter = st.selectbox("도매처 필터", sup_names)

        extra_p = []
        sup_c   = ""
        if sup_filter != "전체":
            sup_c = "AND rq.supplier_name = ?"
            extra_p.append(sup_filter)

        pending = qry(
            "SELECT rq.id, rq.original_name, rq.normalized_attrs, "
            "rq.price, rq.supplier_name "
            "FROM review_queue rq "
            "WHERE rq.status='pending' " + sup_c + " "
            "ORDER BY rq.id DESC LIMIT 200",
            extra_p,
        )

        # 헤더 행
        h0, h1, h2, h3, h4, h5 = st.columns([3, 2, 1, 2, 3, 1])
        for col, lbl in zip([h0,h1,h2,h3,h4,h5],
                            ["원본상품명","도매처","가격","추출결과","표준상품 선택","승인"]):
            col.markdown("**" + lbl + "**")
        st.markdown('<hr style="margin:.3rem 0 .5rem;border-color:#e5e7eb">', unsafe_allow_html=True)

        for item in pending:
            attrs = {}
            try:
                attrs = json.loads(item["normalized_attrs"] or "{}")
            except Exception:
                pass

            pname    = attrs.get("product_name") or ""
            extracted = " / ".join(
                x for x in [pname, attrs.get("grade") or "", attrs.get("weight") or ""] if x
            ) or "-"

            r0, r1, r2, r3, r4, r5 = st.columns([3, 2, 1, 2, 3, 1])
            r0.write(item["original_name"])
            r1.write(item["supplier_name"] or "-")
            r2.write("₩{:,}".format(item["price"]) if item["price"] else "-")
            r3.write(extracted)

            with r4:
                default_idx = 0
                if pname:
                    for i, k in enumerate(sp_keys):
                        if k.lower().startswith(pname.lower()):
                            default_idx = i
                            break
                chosen = st.selectbox(
                    "선택", sp_keys,
                    index=default_idx,
                    key="sp_" + str(item["id"]),
                    label_visibility="collapsed",
                )

            with r5:
                if st.button("승인", key="ok_" + str(item["id"])):
                    sp_id   = sp_map[chosen]
                    sp_name = chosen.split(" (")[0]
                    alias   = (pname or item["original_name"]).strip()
                    try:
                        run_sql(
                            "INSERT OR IGNORE INTO product_aliases "
                            "(alias, standard_product_id, standard_name) VALUES (?,?,?)",
                            (alias, sp_id, sp_name),
                        )
                        run_sql(
                            "UPDATE review_queue SET status='approved', "
                            "reviewed_at=datetime('now','localtime') WHERE id=?",
                            (item["id"],),
                        )
                        st.rerun()
                    except Exception as e:
                        st.error(str(e))

            st.markdown('<hr style="margin:.1rem 0;border-color:#f3f4f6">', unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════
# TAB 3 — 가격표 업데이트
# ═══════════════════════════════════════════════════════════════════

with tab_import:
    st.subheader("가격표 업데이트")
    st.caption("도매처에서 받은 가격표 파일을 업로드하면 자동으로 처리됩니다.")

    method        = st.radio("업로드 방법", ["파일 선택", "파일 경로 입력"], horizontal=True)
    supplier_name = st.text_input("도매처명 *", placeholder="예: 업프루트  /  럭키프레시  /  팜시티")

    file_to_import = None

    if method == "파일 선택":
        uploaded = st.file_uploader(
            "파일 선택 (XLSX / HTML / CSV)",
            type=["xlsx", "xls", "html", "htm", "csv"],
        )
        if uploaded:
            suffix = Path(uploaded.name).suffix
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                tmp.write(uploaded.read())
                file_to_import = tmp.name
            st.caption("선택된 파일: {} ({:,} bytes)".format(uploaded.name, uploaded.size))
    else:
        raw_path = st.text_input("파일 경로", placeholder="E:\\Downloads\\공급가목록.xlsx")
        if raw_path:
            if Path(raw_path).exists():
                file_to_import = raw_path
                st.caption("파일 확인 완료: " + raw_path)
            else:
                st.warning("파일을 찾을 수 없습니다.")

    if st.button("▶ 업데이트 시작",
                 disabled=(not supplier_name or not file_to_import),
                 type="primary"):
        from engine.importer import ImportEngine
        with st.spinner("가격표 처리 중..."):
            try:
                stats = ImportEngine().run(file_to_import, supplier_name)
                st.success("업데이트 완료!")
                st.markdown("---")

                card_data = [
                    ("신규 상품",  stats.new_products,   "#f0fdf4", "#bbf7d0", "#15803d"),
                    ("가격 변경",  stats.updated_prices, "#f0fdf4", "#bbf7d0", "#15803d"),
                    ("검수 필요",  stats.new_products,
                     "#fffbeb" if stats.new_products else "#f0fdf4",
                     "#fde68a" if stats.new_products else "#bbf7d0",
                     "#92400e" if stats.new_products else "#15803d"),
                    ("오류",       stats.failed_rows,
                     "#fef2f2" if stats.failed_rows else "#f0fdf4",
                     "#fecaca" if stats.failed_rows else "#bbf7d0",
                     "#b91c1c" if stats.failed_rows else "#15803d"),
                ]
                card_cols = st.columns(4)
                for col, (lbl, val, bg, bd, tc) in zip(card_cols, card_data):
                    col.markdown(
                        '<div style="background:{bg};border:1px solid {bd};'
                        'border-radius:10px;padding:.9rem 1.1rem;text-align:center">'
                        '<div style="font-size:2rem;font-weight:700;color:{tc}">{val}</div>'
                        '<div style="font-size:.8rem;color:{tc};margin-top:.1rem">{lbl}</div>'
                        '</div>'.format(bg=bg, bd=bd, tc=tc, val=val, lbl=lbl),
                        unsafe_allow_html=True,
                    )

                if stats.new_products > 0:
                    st.info(
                        "{}개 상품이 신규 등록되어 검수가 필요합니다. "
                        "'✅ 검수 필요' 탭을 확인해주세요.".format(stats.new_products)
                    )
            except Exception as e:
                st.error("업데이트 실패: " + str(e))


# ═══════════════════════════════════════════════════════════════════
# TAB 4 — 업데이트 이력
# ═══════════════════════════════════════════════════════════════════

with tab_history:
    st.subheader("업데이트 이력")

    history = qry(
        "SELECT ih.id, ih.file_name, s.name AS sup, ih.imported_at, "
        "ih.total_rows, ih.success_rows, ih.failed_rows, "
        "ih.new_products, ih.updated_prices "
        "FROM import_history ih "
        "LEFT JOIN suppliers s ON s.id = ih.supplier_id "
        "ORDER BY ih.imported_at DESC LIMIT 50"
    )

    if not history:
        st.info("업데이트 이력이 없습니다.")
    else:
        df_h = pd.DataFrame(history)
        df_h.columns = ["ID","파일명","도매처","업데이트 시각","전체","성공","오류","신규","가격변경"]
        st.dataframe(df_h, use_container_width=True, hide_index=True)
