"""Run: python -m streamlit run app.py --server.address 127.0.0.1"""
import json
import os
from pathlib import Path
import streamlit as st
from src.application import Clause, extract_pdf, run_document, safety_issue

st.set_page_config(page_title='Singapore Rental Contract Review', page_icon='📄', layout='wide')
st.title('Singapore Rental Contract Review')
st.caption('PE6201 • HDB and private residential • English clauses • Synthetic demonstration only')
st.warning('Research prototype, not legal advice. A pass is a limited comparison, not permission to sign. External quality targets have not been met.')
with st.sidebar:
    st.header('Review settings')
    housing = st.selectbox('Housing type', ['HDB','Private Residential'], key='housing')
    version = st.selectbox('Evidence version', ['v17 — historical CEA comparison', 'v18 — expanded official sources (failed regression)'], key='evidence_version')
    if version.startswith('v18'):
        st.info('v18 recorded regression failed: recall 57.14%, 2 false positives, 2 unsafe non-abstentions. Expanded-scope independent labels remain pending. Offline mode does not execute the two-model pipeline.')
    live_available = os.getenv('RENTAL_ENABLE_LIVE') == '1'
    mode = st.radio('Execution mode', ['Offline — no credits'] + (['Live — paid experimental'] if live_available else []), key='mode')
    st.caption('Offline rules run now. Unsettled clauses show model_needed; no model output is simulated.')
    budget = st.number_input('Agreement budget in US dollars', min_value=.05, max_value=1., value=.25, step=.05)
    paid = st.checkbox('I authorize this review to use paid API credits', disabled=not live_available)
    if st.button('Clear session data'):
        st.session_state.clear()
        st.rerun()

source = st.radio('Input method', ['Paste a clause','Upload a text PDF','Built-in synthetic example'], horizontal=True, key='input_method')
clauses = []
document_text = ''
if source == 'Paste a clause':
    text = st.text_area('English contract clause', height=160, max_chars=6000,
                        placeholder='Paste synthetic clause text. Include conditions and exceptions.')
    document_text = text
    if text.strip(): clauses = [Clause('CL_01',(),text)]
elif source == 'Upload a text PDF':
    upload = st.file_uploader('Synthetic PDF only — maximum 2 MB and 20 pages', type=['pdf'])
    if upload:
        try:
            extracted = extract_pdf(upload.getvalue())
            document_text = '\n'.join(c.text for c in extracted)
            st.caption('Fragments are provisional. Page breaks and headings vary; check them against your PDF. No claim of complete automatic clause segmentation.')
            chosen = st.multiselect('Select fragments to review — maximum 20',
                [c.clause_id for c in extracted], default=[c.clause_id for c in extracted[:20]])
            clauses = [c for c in extracted if c.clause_id in chosen]
            for c in extracted:
                with st.expander(f'{c.clause_id} · PDF page {", ".join(map(str,c.pages))}'):
                    st.text(c.text)
        except ValueError as error: st.error(str(error))
else:
    samples = json.loads((Path(__file__).parent/'data/demo_examples.json').read_text(encoding='utf-8'))
    name = st.selectbox('Example', [s['title'] for s in samples if s['housing_type']==housing])
    sample = next(s for s in samples if s['title']==name)
    st.info(sample['purpose'])
    clauses = [Clause(f'CL_{n:02}', (), text) for n,text in enumerate(sample['clauses'],1)]
    document_text = '\n'.join(c.text for c in clauses)
    for c in clauses: st.text(c.text)

issue = safety_issue(document_text,housing) if document_text else None
if issue: st.error(issue)
synthetic = st.checkbox('All input is synthetic and contains no names, addresses, identity numbers or other personal data', key='synthetic')
checked = st.checkbox('I checked the selected text against the input, including all conditions and exceptions', key='extraction_checked')
if st.button('Review selected clauses', type='primary', key='review', disabled=not clauses or not synthetic or not checked or bool(issue)):
    try:
        with st.spinner('Comparing selected clauses with the housing-specific CEA reference…'):
            st.session_state['report'] = run_document(clauses,housing,synthetic_confirmed=synthetic,
                extraction_confirmed=checked,live=mode.startswith('Live'),spending_confirmed=paid,budget=str(budget),review_version=version[:3])
    except ValueError as error: st.error(str(error))

report = st.session_state.get('report')
if report:
    st.divider()
    st.header('Review report')
    st.caption(f"Saved result • {report['version']} • {report['housing_type']} • {report['mode']} • selected fragments only. Changing inputs does not rerun this report.")
    if report['version']=='v18':
        st.info(report['evaluation_status']+'. '+report['offline_scope'] if report['mode']=='offline' else report['evaluation_status'])
    cols = st.columns(3)
    cols[0].metric('Selected fragments processed', len(report['clauses']))
    cols[1].metric('API calls', report['accounting']['api_calls'])
    cols[2].metric('Reported cost US dollars', report['accounting']['cost_usd'])
    if report['stopped']:
        st.error('Review stopped. Earlier results remain visible; no automatic retry. Some charges may be unknown.')
    labels = {'review_required':'Clarify a supported potential risk',
              'no_material_difference_found':'No material adverse difference found in this comparison',
              'insufficient_evidence':'Evidence insufficient — no conclusion'}
    for row in report['clauses']:
        st.subheader(row['clause_id'])
        st.text(row['text'])
        if row.get('retrieved_sources'):
            with st.expander('Retrieved reference locations — retrieval is not proof of support'):
                for reference in row['retrieved_sources']:
                    st.write(f"{reference['source_id']} · {reference['section']} · {reference['source_kind']}")
                    if reference['url']: st.link_button('Official source',reference['url'])
        if row['status'] == 'model_needed':
            st.info('model_needed — local rules cannot settle this clause. No model ran and no completed prediction is claimed.')
            continue
        if row['status'] == 'stopped':
            st.error('Not assessed because execution stopped.'); continue
        result = row['result']
        st.write(labels[result['label']])
        st.code(result['label'], language=None)
        st.write(result['reason'])
        if result['follow_up_question']: st.write('Ask:',result['follow_up_question'])
        for ev in result['evidence']:
            with st.expander(f"{ev['source_id']} · {ev['source_section']}", expanded=True):
                st.text(ev['quote'])
                if ev.get('context_quote'):
                    st.caption('Full registered context')
                    st.text(ev['context_quote'])
    st.download_button('Download report JSON', json.dumps(report,ensure_ascii=False,indent=2),
                        'rental_review_report.json','application/json')
with st.expander('Recorded v16 evaluation and limits'):
    st.write('Original live run on 20 AI-authored external-source diagnostic cases. Not expert-blind gold. Preserved unchanged after v17 regression.')
    st.table({'Measure':['Risk precision','Risk recall','Unsafe non-abstention (lower better)','Citation locator validity','Substantive citation support'],
              'v16 RAG':['1/2 (50%)','1/14 (7.14%)','2/4 (50%)','4/4 (100%)','1/4 (25%), assistant first pass'],
              'Keyword baseline':['3/4 (75%)','3/14 (21.43%)','4/4 (100%)','Not audited','Not assessed']})
    st.caption('16/20 RAG results abstained. Cost US$0.2383215, 29 calls, 83,563 tokens. Owner confirmation of citation audit pending. 95% goal unmet.')
with st.expander('Recorded v17 regression and limits'):
    st.write('One separately authorized paid regression on the same exposed 20 cases, unchanged labels. Not an independent generalization test. Correct labels do not certify correct explanations.')
    st.table({'Measure':['Risk precision','Risk recall','Unsafe non-abstention (lower better)','Citation locator validity','Substantive citation support'],
              'v17 RAG':['5/5 (100%)','5/14 (35.71%)','0/4 (0%)','6/6 (100%)','2/6 (33.33%), assistant first pass'],
              'Unchanged keyword baseline':['3/4 (75%)','3/14 (21.43%)','4/4 (100%)','Not audited','Not assessed']})
    st.caption('14/20 RAG results abstained. Cost USD 0.2722430, 36 calls, 99,584 tokens. Both runs total USD 0.5105645. Citation audit awaits owner confirmation; uncertain items count as failures. Recall and 95% substantive-support goals remain unmet. No paid API call is made by opening this table.')
with st.expander('Recorded v18 regression and v19 offline candidate'):
    summary=json.loads((Path(__file__).parent/'data/evaluation_summary_v18.json').read_text(encoding='utf-8'))
    st.write(summary['evaluation_scope'])
    st.table({'Measure':['Risk precision','Risk recall','False positives','Unsafe non-abstention','Citation locator validity','Substantive citation support'],
              'v18':['8/10 (80%)','8/14 (57.14%)','2','2/4 (50%)','12/12 (100%)','0/12 (0%), strict assistant first pass']})
    st.caption('8/20 abstained. US$0.6162670, 40 calls, 194,224 tokens. Every released assertion is audited; unsupported neighbors fail the response. Owner confirmation pending. Failed acceptance; not a final product.')
    st.info(summary['v19_status'])
st.caption('No uploaded PDF is saved to disk by this app. Text stays in server session memory until cleared/closed. Personal-data detection is incomplete; do not upload real contracts. Live mode requires server enablement and explicit confirmation.')
