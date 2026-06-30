"""
PaldoDamdA OS - Streamlit Web App v1
바로 쓰는 도매처 가격검색 + Review Queue 관리

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

# ─── Page config ───────────────────────────────────────────────────
st.set_page_config(
    page_title="PaldoDamdA OS",
    page_icon="🌾",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown("""
<style>
  .block-container{padding-top:1.2rem}
  .best-card{
    background:linear-gradient(135deg,#1a7f37,#2ea04f);
    color:white;border-radius:12px;padding:1.2rem 1.6rem;margin-bottom:1rem
  }
  .best-card h2{margin:0;font-size:1.6rem}
  .best-card p{margin:.2rem 0 0;font-size:.9rem;opacity:.9}
</style>
""", unsafe_allow_html=True)


# ─── DB helpers ─────────────────────────────────────────────────────

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


# ─── Header + Tabs ──────────────────────────────────────────────────

st.title("🌾 PaldoDamdA OS")
tab_search, tab_review, tab_import, tab_history = st.tabs([
    "🔍 상품 검색", "📋 Review Queue", "📂 Import", "📜 Import 이력",
])


# ═══════════════════════════════════════════════════════════════════
# TAB 1 — 상품 검색 + 가격 비교
# ═══════════════════════════════════════════════════════════════════

with tab_search:
    st.subheader("상품 검색")

    col_q, col_cat = st.columns([4, 1])
    with col_q:
        q_text = st.text_input(
            "검색어",
            placeholder="신비복숭아 / 참외 / 초당옥수수 / 애플망고 / 전복",
            label_visibility="collapsed",
        )
    with col_cat:
        cats = ["전체"] + [r["category"] for r in qry(
            "SELECT DISTINCT category FROM standard_products "
            "WHERE category IS NOT NULL ORDER BY category"
        )]
        cat = st.selectbox("카테고리", cats, label_visibility="collapsed")

    if q_text or cat != "전체":
        like = "%" + q_text + "%" if q_text else "%"
        search_params = [like, like]
        cat_clause = ""
        if cat != "전체":
            cat_clause = "AND sp.category = ?"
            search_params.append(cat)

        products = qry(
            "SELECT sp.id, sp.standard_name, sp.category, "
            "COUNT(po.id) AS offer_count, "
            "MIN(po.price) AS min_price, MAX(po.price) AS max_price "
            "FROM standard_products sp "
            "LEFT JOIN product_offers po "
            "ON po.standard_product_id = sp.id "
            "AND po.needs_review = 0 AND po.price > 0 "
            "WHERE (sp.standard_name LIKE ? "
            "OR sp.id IN ("
            "SELECT standard_product_id FROM product_aliases WHERE alias LIKE ? "
            ")) " + cat_clause + " "
            "GROUP BY sp.id "
            "ORDER BY offer_count DESC, sp.standard_name",
            search_params,
        )

        if not products:
            st.info("검색 결과가 없습니다.")
        else:
            st.caption(str(len(products)) + "개 상품 발견")
            n_cols = min(len(products), 4)
            cols = st.columns(n_cols)
            for i, p in enumerate(products):
                price_str = (
                    "₩{:,} ~ ₩{:,}".format(p["min_price"], p["max_price"])
                    if p["min_price"] else "가격 없음"
                )
                label = "{}\n\n{} | {}개 도매처\n\n{}".format(
                    p["standard_name"], p["category"] or "", p["offer_count"], price_str,
                )
                with cols[i % n_cols]:
                    if st.button(label, key="prod_" + str(p["id"]), use_container_width=True):
                        st.session_state["selected_product"] = p

    # ── 가격 비교 ──────────────────────────────────────────────────
    if "selected_product" in st.session_state:
        p = st.session_state["selected_product"]
        st.divider()

        offers = qry(
            "SELECT s.name AS sup, po.price AS price, "
            "ri.raw_product_name AS orig, ri.raw_option AS opt, "
            "po.weight_value AS wv, po.weight_unit AS wu, "
            "po.quantity_value AS cv, po.quantity_unit AS cu, "
            "po.quality_grade AS grade, po.cultivation_type AS cult, "
            "po.package_type AS pkg, po.attributes AS tag, "
            "po.status AS status, "
            "po.jeju_available AS jeju, po.jeju_extra_fee AS jeju_fee, "
            "po.island_available AS island, po.island_extra_fee AS island_fee, "
            "sf.received_date AS fdate, sf.file_name AS fname "
            "FROM product_offers po "
            "JOIN suppliers s ON s.id = po.supplier_id "
            "LEFT JOIN raw_items ri ON ri.id = po.raw_item_id "
            "LEFT JOIN source_files sf ON sf.id = ri.source_file_id "
            "WHERE po.standard_product_id = ? "
            "AND po.needs_review = 0 "
            "AND po.price IS NOT NULL AND po.price > 0 "
            "ORDER BY po.price ASC",
            [p["id"]],
        )

        if offers:
            best = offers[0]
            w_str = "{}{}".format(best["wv"], best["wu"]) if best["wv"] else ""
            c_str = "{}{}".format(best["cv"], best["cu"]) if best["cv"] else ""
            spec  = " / ".join(x for x in [w_str, c_str, best["grade"]] if x)

            st.markdown(
                '<div class="best-card">'
                '<h2>🏆 최저가 &nbsp; ₩{price:,}</h2>'
                '<p>{sup} &nbsp;·&nbsp; {spec} &nbsp;·&nbsp; '
                '제주 {jeju} &nbsp;·&nbsp; 도서 {island}</p>'
                '<p style="opacity:.7;font-size:.85rem">{orig}</p>'
                '</div>'.format(
                    price=best["price"],
                    sup=best["sup"],
                    spec=spec or "규격 미상",
                    jeju=best["jeju"] or "-",
                    island=best["island"] or "-",
                    orig=best["orig"] or "",
                ),
                unsafe_allow_html=True,
            )

            st.markdown("#### {} — 도매처별 가격 비교 ({}건)".format(
                p["standard_name"], len(offers)
            ))

            rows = []
            for rank, o in enumerate(offers, 1):
                w = "{}{}".format(o["wv"], o["wu"]) if o["wv"] else ""
                c = "{}{}".format(o["cv"], o["cu"]) if o["cv"] else ""
                rows.append({
                    "#":        rank,
                    "도매처":   o["sup"],
                    "공급가":   "₩{:,}".format(o["price"]),
                    "원본상품명": o["orig"] or "",
                    "옵션":     o["opt"] or "",
                    "중량":     w,
                    "입수":     c,
                    "등급":     o["grade"] or "",
                    "재배":     o["cult"] or "",
                    "포장":     o["pkg"] or "",
                    "태그":     o["tag"] or "",
                    "출하":     o["status"] or "",
                    "제주":     o["jeju"] or "",
                    "제주비":   "₩{:,}".format(o["jeju_fee"]) if o["jeju_fee"] else "",
                    "도서":     o["island"] or "",
                    "도서비":   "₩{:,}".format(o["island_fee"]) if o["island_fee"] else "",
                    "파일날짜": o["fdate"] or "",
                })

            df = pd.DataFrame(rows)
            st.dataframe(df, use_container_width=True, hide_index=True)

            with st.expander("📥 CSV 다운로드"):
                csv = df.to_csv(index=False, encoding="utf-8-sig")
                st.download_button(
                    "CSV 저장",
                    data=csv,
                    file_name="{}_가격비교.csv".format(p["standard_name"]),
                    mime="text/csv",
                )
        else:
            st.info("이 상품의 가격 데이터가 없습니다.")

        if st.button("✕ 선택 해제", key="clear_sel"):
            del st.session_state["selected_product"]
            st.rerun()


# ═══════════════════════════════════════════════════════════════════
# TAB 2 — Review Queue
# ═══════════════════════════════════════════════════════════════════

with tab_review:
    st.subheader("Review Queue — 검수 필요 상품")

    n_pending  = qry("SELECT COUNT(*) AS n FROM review_queue WHERE status='pending'")[0]["n"]
    n_approved = qry("SELECT COUNT(*) AS n FROM review_queue WHERE status='approved'")[0]["n"]
    n_sp       = qry("SELECT COUNT(*) AS n FROM standard_products")[0]["n"]

    c1, c2, c3 = st.columns(3)
    c1.metric("검수 대기", "{:,}건".format(n_pending))
    c2.metric("승인 완료", "{:,}건".format(n_approved))
    c3.metric("표준 상품", "{}개".format(n_sp))

    sp_list = qry(
        "SELECT id, standard_name, category FROM standard_products "
        "ORDER BY category, standard_name"
    )
    sp_map = {"{} ({})".format(r["standard_name"], r["category"]): r["id"] for r in sp_list}

    st.divider()

    sup_names = ["전체"] + sorted({
        r["supplier_name"] for r in qry(
            "SELECT DISTINCT supplier_name FROM review_queue "
            "WHERE status='pending' AND supplier_name IS NOT NULL"
        )
    })
    sup_filter = st.selectbox("도매처 필터", sup_names)

    extra_params = []
    sup_clause   = ""
    if sup_filter != "전체":
        sup_clause = "AND rq.supplier_name = ?"
        extra_params.append(sup_filter)

    pending = qry(
        "SELECT rq.id, rq.original_name, rq.normalized_attrs, "
        "rq.price, rq.supplier_name, rq.file_name, rq.created_at "
        "FROM review_queue rq "
        "WHERE rq.status = 'pending' " + sup_clause + " "
        "ORDER BY rq.id DESC LIMIT 100",
        extra_params,
    )

    if not pending:
        st.success("검수 대기 항목이 없습니다. 🎉")
    else:
        for item in pending:
            attrs = {}
            try:
                attrs = json.loads(item["normalized_attrs"] or "{}")
            except Exception:
                pass

            price_disp = "₩{:,}".format(item["price"]) if item["price"] else "가격없음"
            exp_title  = "[{}] {}  |  {}  |  {}".format(
                item["id"], item["original_name"],
                item["supplier_name"] or "?", price_disp,
            )

            with st.expander(exp_title, expanded=False):
                left, right = st.columns([2, 3])

                with left:
                    st.markdown("**원본 정보**")
                    st.write("- 원본명: `{}`".format(item["original_name"]))
                    st.write("- 도매처: {}".format(item["supplier_name"] or "-"))
                    st.write("- 파일: {}".format(item["file_name"] or "-"))
                    st.write("- 입력일: {}".format((item["created_at"] or "")[:10]))

                with right:
                    st.markdown("**Normalizer 추출 결과**")
                    st.write("- 추출 상품명: `{}`".format(attrs.get("product_name", "-")))
                    st.write("- 등급: {}".format(attrs.get("grade") or "-"))
                    st.write("- 중량: {}".format(attrs.get("weight") or "-"))
                    cnt      = attrs.get("count")
                    cnt_unit = attrs.get("count_unit", "")
                    st.write("- 입수: {}".format("{}{}".format(cnt, cnt_unit) if cnt else "-"))
                    st.write("- 재배: {}".format(attrs.get("cultivation_type") or "-"))
                    st.write("- 태그: {}".format(", ".join(attrs.get("tags", [])) or "-"))

                st.markdown("---")
                sc1, sc2, sc3 = st.columns([3, 2, 1])

                with sc1:
                    chosen = st.selectbox(
                        "표준 상품 선택", list(sp_map.keys()),
                        key="sp_" + str(item["id"]),
                    )
                with sc2:
                    default_alias = attrs.get("product_name") or item["original_name"]
                    alias_val = st.text_input(
                        "등록할 Alias", value=default_alias,
                        key="alias_" + str(item["id"]),
                    )
                with sc3:
                    st.markdown("<br>", unsafe_allow_html=True)
                    if st.button("✅ 승인", key="approve_" + str(item["id"])):
                        sp_id   = sp_map[chosen]
                        sp_name = chosen.split(" (")[0]
                        a_val   = alias_val.strip()
                        try:
                            run_sql(
                                "INSERT OR IGNORE INTO product_aliases "
                                "(alias, standard_product_id, standard_name) VALUES (?,?,?)",
                                (a_val, sp_id, sp_name),
                            )
                            run_sql(
                                "UPDATE review_queue SET status='approved', "
                                "reviewed_at=datetime('now','localtime') WHERE id=?",
                                (item["id"],),
                            )
                            st.success("✅ 승인: `{}` → {}".format(a_val, sp_name))
                            st.rerun()
                        except Exception as e:
                            st.error("오류: {}".format(e))


# ═══════════════════════════════════════════════════════════════════
# TAB 3 — Import
# ═══════════════════════════════════════════════════════════════════

with tab_import:
    st.subheader("데이터 Import")
    st.info("도매처 파일(XLSX / HTML / CSV)을 업로드하거나 파일 경로를 입력해서 Import를 실행합니다.")

    method        = st.radio("Import 방법", ["파일 업로드", "파일 경로 입력"], horizontal=True)
    supplier_name = st.text_input("도매처명 *", placeholder="예: 업프루트, 럭키프레시, 팜시티")

    file_to_import = None

    if method == "파일 업로드":
        uploaded = st.file_uploader(
            "파일 선택 (XLSX / HTML / CSV)", type=["xlsx", "xls", "html", "htm", "csv"]
        )
        if uploaded:
            suffix = Path(uploaded.name).suffix
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                tmp.write(uploaded.read())
                file_to_import = tmp.name
            st.caption("파일: {} ({:,} bytes)".format(uploaded.name, uploaded.size))
    else:
        raw_path = st.text_input("파일 경로", placeholder="E:\\Downloads\\공급가목록.xlsx")
        if raw_path:
            if Path(raw_path).exists():
                file_to_import = raw_path
                st.caption("파일 확인: {}".format(raw_path))
            else:
                st.warning("파일을 찾을 수 없습니다.")

    btn_disabled = not supplier_name or not file_to_import
    if st.button("▶ Import 실행", disabled=btn_disabled, type="primary"):
        from engine.importer import ImportEngine
        with st.spinner("Import 중..."):
            try:
                stats = ImportEngine().run(file_to_import, supplier_name)
                st.success("Import 완료!")
                m1, m2, m3, m4, m5 = st.columns(5)
                m1.metric("전체",     stats.total_rows)
                m2.metric("성공",     stats.success_rows)
                m3.metric("검수 필요", stats.new_products)
                m4.metric("오류",     stats.failed_rows)
                m5.metric("가격 변경", stats.updated_prices)
                if stats.new_products > 0:
                    st.warning(
                        "{}개 상품이 Review Queue에 추가됐습니다. "
                        "📋 Review Queue 탭에서 확인해주세요.".format(stats.new_products)
                    )
            except Exception as e:
                st.error("Import 실패: {}".format(e))


# ═══════════════════════════════════════════════════════════════════
# TAB 4 — Import 이력
# ═══════════════════════════════════════════════════════════════════

with tab_history:
    st.subheader("Import 이력")

    history = qry(
        "SELECT ih.id, ih.file_name, s.name AS supplier_name, ih.imported_at, "
        "ih.total_rows, ih.success_rows, ih.failed_rows, "
        "ih.new_products, ih.updated_prices "
        "FROM import_history ih "
        "LEFT JOIN suppliers s ON s.id = ih.supplier_id "
        "ORDER BY ih.imported_at DESC LIMIT 50"
    )

    if not history:
        st.info("Import 이력이 없습니다.")
    else:
        df_h = pd.DataFrame(history)
        df_h.columns = [
            "ID", "파일명", "도매처", "Import 시각",
            "전체", "성공", "오류", "검수필요", "가격변경",
        ]
        st.dataframe(df_h, use_container_width=True, hide_index=True)
