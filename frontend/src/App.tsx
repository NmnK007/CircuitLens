import { useEffect, useMemo, useState } from 'react';
import { Activity, AlertTriangle, CircuitBoard, Cpu, FileImage, FlaskConical, Play, Upload } from 'lucide-react';
import { analyzeImage, explainSimulation, fetchHealth, fetchSeededCircuit, simulateCircuit, validateCircuit } from './api/client';
import type { CircuitModel, GroundedExplanation, ImageAnalysisResult, ImageCandidate, SimulationResult, WaveformTrace } from './types/circuit';

type ReviewCandidate = ImageCandidate & { valueDraft: string; unitDraft: string; nodesDraft: string; confirmed: boolean };

function Waveform({ trace }: { trace?: WaveformTrace }) {
  if (!trace || trace.x.length < 2 || trace.y.length !== trace.x.length) {
    return <div className="chart-empty">Run a simulation to see actual ngspice samples here.</div>;
  }
  const width = 800, height = 260, left = 52, right = 22, top = 18, bottom = 38;
  const minY = Math.min(0, ...trace.y), maxY = Math.max(1, ...trace.y), range = maxY - minY || 1;
  const maxX = trace.x[trace.x.length - 1] || 1;
  const points = trace.x.map((x, i) => `${left + x / maxX * (width - left - right)},${top + (maxY - trace.y[i]) / range * (height - top - bottom)}`).join(' ');
  return <svg className="waveform" viewBox={`0 0 ${width} ${height}`} role="img" aria-label={`${trace.name} actual ngspice voltage waveform`}>
    <line x1={left} y1={top} x2={left} y2={height-bottom} className="axis"/><line x1={left} y1={height-bottom} x2={width-right} y2={height-bottom} className="axis"/>
    {[0, .25, .5, .75, 1].map((q) => <g key={q}><line x1={left} x2={width-right} y1={top+q*(height-top-bottom)} y2={top+q*(height-top-bottom)} className="gridline"/><text x={left-10} y={top+q*(height-top-bottom)+4} textAnchor="end" className="tick">{(maxY-q*range).toFixed(1)} V</text></g>)}
    <polyline points={points} className="curve"/><text x={left} y={height-10} className="tick">0 ms</text><text x={width-right} y={height-10} textAnchor="end" className="tick">{(maxX*1000).toFixed(0)} ms</text>
  </svg>;
}

export default function App() {
  const [circuit, setCircuit] = useState<CircuitModel | null>(null);
  const [result, setResult] = useState<SimulationResult | null>(null);
  const [health, setHealth] = useState<{ ngspice_available: boolean; gemma_provider: string; gemma_model: string; gemma_available: boolean } | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [image, setImage] = useState('');
  const [imageName, setImageName] = useState('');
  const [draftValues, setDraftValues] = useState<Record<string, string>>({});
  const [imageFile, setImageFile] = useState<File | null>(null);
  const [analysis, setAnalysis] = useState<ImageAnalysisResult | null>(null);
  const [reviewCandidates, setReviewCandidates] = useState<ReviewCandidate[]>([]);
  const [analyzing, setAnalyzing] = useState(false);
  const [topologyConfirmed, setTopologyConfirmed] = useState(false);
  const [question, setQuestion] = useState('Explain the simulated output and time constant.');
  const [explanation, setExplanation] = useState<GroundedExplanation | null>(null);
  const [explaining, setExplaining] = useState(false);

  useEffect(() => {
    fetchHealth().then(setHealth).catch(() => setError('Backend is not connected. Start the FastAPI service, then reload this page.'));
    fetchSeededCircuit().then((seed) => { setCircuit(seed); run(seed); }).catch(() => setError('Could not load the seeded circuit. Check the backend and try again.'));
  }, []);

  async function run(current = circuit) {
    if (!current) return;
    setBusy(true); setError(''); setResult(null);
    try { setResult(await simulateCircuit(current)); }
    catch (e) { setError(e instanceof Error ? e.message : 'Simulation request failed.'); }
    finally { setBusy(false); }
  }
  async function analyzeSelectedImage() {
    if (!imageFile) return;
    setAnalyzing(true); setError(''); setAnalysis(null);
    try {
      const result = await analyzeImage(imageFile);
      setAnalysis(result);
      setReviewCandidates(result.components.map((item) => ({
        ...item,
        valueDraft: item.value_magnitude == null ? '' : String(item.value_magnitude),
        unitDraft: item.value_unit || ({ resistor: 'ohm', capacitor: 'F', voltage_source_dc: 'V' } as Record<string,string>)[item.type] || 'ohm',
        nodesDraft: item.terminal_candidates.join(', '),
        confirmed: false,
      })));
      setTopologyConfirmed(false);
    } catch (e) { setError(e instanceof Error ? e.message : 'Gemma image analysis failed.'); }
    finally { setAnalyzing(false); }
  }
  async function applyReviewedCircuit() {
    if (!topologyConfirmed || reviewCandidates.some((c) => !c.confirmed)) {
      setError('Confirm each component and the overall connection review before applying this circuit.'); return;
    }
    const components = reviewCandidates.filter((item) => item.type !== 'ground').map((item) => ({
      id: item.id,
      type: item.type,
      value: { magnitude: Number(item.valueDraft), unit: item.unitDraft },
      terminals: item.nodesDraft.split(',').map((node) => node.trim()),
      initial_voltage: 0,
      confidence: item.confidence,
      is_uncertain: false,
    }));
    const candidate: CircuitModel = {
      schema_version: '1.0', name: imageName || 'Reviewed schematic', description: 'User-reviewed image candidates',
      analysis: 'transient', ground_node: '0', components,
      simulation: { type: 'transient', step_seconds: 0.00001, stop_seconds: 0.05 },
      ambiguities: [], source_image_name: imageName,
    };
    try {
      const verdict = await validateCircuit(candidate);
      if (!verdict.valid) { setError(`Circuit needs correction: ${verdict.errors.join(' ')}`); return; }
      setCircuit(verdict.normalized_circuit || candidate); setResult(null); setExplanation(null); setError('');
    } catch (e) { setError(e instanceof Error ? e.message : 'Circuit validation failed.'); }
  }
  async function askGemma() {
    if (!circuit || !result || result.status !== 'success') return;
    setExplaining(true); setError('');
    try { setExplanation(await explainSimulation(circuit, result, question)); }
    catch (e) { setError(e instanceof Error ? e.message : 'Gemma explanation failed.'); }
    finally { setExplaining(false); }
  }
  function updateMagnitude(id: string, magnitude: number) {
    if (!circuit || !Number.isFinite(magnitude) || magnitude <= 0) return;
    setCircuit({ ...circuit, components: circuit.components.map((item) => item.id === id ? { ...item, value: { ...item.value, magnitude } } : item) });
    setResult(null);
  }
  const resistor = circuit?.components.find((c) => c.type === 'resistor');
  const capacitor = circuit?.components.find((c) => c.type === 'capacitor');
  const tauMs = useMemo(() => resistor && capacitor ? resistor.value.magnitude * capacitor.value.magnitude * 1000 : 0, [resistor, capacitor]);
  const out = result?.traces.find((trace) => trace.name.toLowerCase() === 'v(out)') || result?.traces[0];

  return <div className="app-shell">
    <header className="topbar"><a className="brand" href="#"><span className="brand-mark"><CircuitBoard size={21}/></span> CircuitLens <span className="brand-tag">LAB / 01</span></a><div className="top-status"><span className={`dot ${health?.ngspice_available ? 'green' : ''}`}/>{health?.ngspice_available ? 'ngspice ready' : 'checking simulator'}<span className="divider"/><Cpu size={15}/>{health?.gemma_available ? `Gemma ready · ${health.gemma_model}` : 'Gemma unavailable · Ollama/model not found'}</div></header>
    <main>
      <div className="page-heading"><div><div className="eyebrow">ENGINEERING WORKSPACE <span>•</span> EDUCATIONAL PROTOTYPE</div><h1>Understand your circuit.</h1><p>Load the verified RC example, adjust component values, and inspect real ngspice results.</p></div><button className="secondary-button" onClick={() => { fetchSeededCircuit().then((seed) => { setCircuit(seed); setDraftValues({}); setImage(''); setImageFile(null); setImageName(''); setAnalysis(null); setReviewCandidates([]); setResult(null); setError(''); }); }}><Activity size={16}/> Reset example</button></div>
      {error && <div className="notice error"><AlertTriangle size={18}/><span>{error}</span></div>}
      <section className="work-grid">
        <div className="main-column">
          <section className="panel circuit-panel"><div className="panel-header"><div><div className="eyebrow">01 / CIRCUIT INPUT</div><h2>{imageName || circuit?.name || 'Seeded RC charge'}</h2></div><div className="header-actions"><label className="secondary-button upload-button"><Upload size={16}/> Choose PNG/JPG<input type="file" accept="image/png,image/jpeg" onChange={(e) => { const file=e.target.files?.[0]; if(file){ if(file.size>10*1024*1024){setError('Image must be smaller than 10 MB.');return;} setImage(URL.createObjectURL(file)); setImageFile(file); setImageName(file.name); setAnalysis(null); } }}/></label><button className="secondary-button" onClick={analyzeSelectedImage} disabled={!imageFile||analyzing||!health?.gemma_available}>{analyzing?'Analyzing…':'Analyze with Gemma'}</button></div></div>
            {image ? <div className="image-preview"><img src={image} alt={`Uploaded schematic preview: ${imageName}`}/><div><FileImage size={16}/>{analysis?`Gemma candidates · ${analysis.components.length} component(s) · review required`:'Choose Analyze with Gemma to inspect this schematic.'}</div></div> : <div className="schematic" aria-label="Seeded RC circuit diagram"><svg viewBox="0 0 760 210" role="img" aria-label="5 volt source, resistor, capacitor to ground"><path d="M84 105 H230 M330 105 H470 M470 105 V152 M470 152 H625 M84 105 V152 M84 152 H625"/><circle cx="84" cy="105" r="4"/><circle cx="470" cy="105" r="4"/><path d="M230 105 l10 -12 18 24 18 -24 18 24 18 -24 18 12"/><path d="M470 152 V163 M452 163 H488 M458 171 H482 M464 179 H476"/><circle cx="84" cy="130" r="17"/><path d="M84 120 V140 M77 130 H91"/><text x="65" y="93">V1 · 5 V</text><text x="250" y="77">R1 · {resistor ? (resistor.value.magnitude/1000).toPrecision(3).replace(/\.?0+$/,'')+' kΩ' : '1 kΩ'}</text><text x="493" y="123">Vout</text><text x="490" y="194">C1 · {capacitor ? (capacitor.value.magnitude*1e6).toPrecision(3).replace(/\.?0+$/,'')+' μF' : '10 μF'}</text><text x="605" y="174">GND</text></svg><div className="schematic-caption"><span><i className="legend-line"/>Confirmed seeded connectivity</span><span>5 V step · capacitor starts at 0 V</span></div></div>}
          </section>
          {analysis && <section className="panel review-panel"><div className="eyebrow">IMAGE INTERPRETATION / USER REVIEW REQUIRED</div><h2>Candidate components</h2><p className="muted">Gemma's visual confidence is not a calibrated probability. Correct values and both terminal nodes; use node 0 for ground connections.</p>{reviewCandidates.map((item,index)=><div className="review-row" key={`${index}-${item.id}`}><label className="review-check"><input type="checkbox" checked={item.confirmed} onChange={(e)=>setReviewCandidates(reviewCandidates.map((c,i)=>i===index?{...c,confirmed:e.target.checked}:c))}/></label><div className="review-main"><div className="review-fields"><input aria-label="Component ID" value={item.id} onChange={(e)=>setReviewCandidates(reviewCandidates.map((c,i)=>i===index?{...c,id:e.target.value}:c))}/><strong>{item.type.replace(/_/g,' ')}</strong></div><small>{item.visual_evidence||'No visual evidence returned'} · model estimate {(item.confidence*100).toFixed(0)}%</small><div className="review-fields"><input aria-label={`${item.id} value`} placeholder="SI value" value={item.valueDraft} onChange={(e)=>setReviewCandidates(reviewCandidates.map((c,i)=>i===index?{...c,valueDraft:e.target.value}:c))}/><input aria-label={`${item.id} unit`} placeholder="unit" value={item.unitDraft} onChange={(e)=>setReviewCandidates(reviewCandidates.map((c,i)=>i===index?{...c,unitDraft:e.target.value}:c))}/><input aria-label={`${item.id} terminal nodes`} placeholder="node1, node2" value={item.nodesDraft} onChange={(e)=>setReviewCandidates(reviewCandidates.map((c,i)=>i===index?{...c,nodesDraft:e.target.value}:c))}/></div></div></div>)}<div className="review-warnings">{analysis.observed_text.length>0&&<p><b>Text read:</b> {analysis.observed_text.join(' · ')}</p>}{analysis.ambiguities.map((a,i)=><p key={`a${i}`}><AlertTriangle size={13}/>{a}</p>)}{analysis.unsupported_symbols.map((a,i)=><p key={`u${i}`}>Unsupported symbol: {a}</p>)}<p>{analysis.line_segments.length} line segment hint(s) from image geometry. Crossings do not imply a connection.</p></div><label className="acknowledge"><input type="checkbox" checked={topologyConfirmed} onChange={(e)=>setTopologyConfirmed(e.target.checked)}/> I reviewed the component values, every terminal-node assignment, and the marked crossings.</label><button className="run-button" onClick={applyReviewedCircuit}>Apply reviewed circuit</button><p className="microcopy">Applying still requires backend electrical validation. The simulator will reject any model that retains ambiguity flags.</p></section>}
          <section className="panel results-panel"><div className="panel-header"><div><div className="eyebrow">02 / SIMULATION</div><h2>Transient response</h2></div>{result?.status==='success' && <span className="result-badge"><span className="dot green"/> SIMULATED</span>}</div><div className="chart-wrap"><div className="chart-title"><span>Output node <b>V(out)</b></span><span>Voltage <b>V</b></span></div><Waveform trace={out}/></div>
            <div className="metrics"><div><span>TIME CONSTANT</span><strong>{tauMs.toFixed(2)} <small>ms</small></strong><em>R × C</em></div><div><span>FINAL OUTPUT</span><strong>{result?.status==='success' && result.summary.final_voltage !== undefined ? `${result.summary.final_voltage.toFixed(3)} V` : '—'}</strong><em>from ngspice samples</em></div><div><span>SAMPLES</span><strong>{result?.status==='success' ? result.summary.num_time_points ?? '—' : '—'}</strong><em>actual parsed data points</em></div></div>
            {result?.theory_verification && <div className={`notice ${result.theory_verification.passed_tolerance?'success':'warn'}`}><FlaskConical size={17}/><span>RC check: {result.theory_verification.explanation} Tolerance {result.theory_verification.tolerance_percent}%.</span></div>}
            {result?.status==='unavailable' && <div className="notice warn"><AlertTriangle size={17}/><span>ngspice is unavailable. No simulated waveform is shown.</span></div>}
            {result?.status==='error' && <div className="notice error"><AlertTriangle size={17}/><span>{result.error_message || 'ngspice did not return usable simulation data.'} No waveform is shown.</span></div>}
          </section>
        </div>
        <aside className="side-column"><section className="panel editor-panel"><div className="eyebrow">03 / MODEL EDITOR</div><h2>Components</h2><p className="muted">Change a value, then run the circuit again.</p>
            {circuit?.components.filter((c)=>c.type==='voltage_source_dc').map((component)=><div className="component-row" key={component.id}><div className="component-icon source">V</div><div className="component-meta"><strong>{component.id} <span>DC source</span></strong><small>{component.terminals.join(' → ')}</small></div><div className="component-value">{component.value.magnitude} V</div></div>)}
            {circuit?.components.filter((c)=>c.type==='resistor'||c.type==='capacitor').map((component)=>{const isResistor=component.type==='resistor';return <div className="component-row" key={component.id}><div className={`component-icon ${isResistor?'resistor':'capacitor'}`}>{isResistor?'R':'C'}</div><div className="component-meta"><strong>{component.id} <span>{isResistor?'Resistor':'Capacitor'}</span></strong><small>{component.terminals.join(' → ')}</small></div><input className="value-input" aria-label={`${component.id} SI value`} type="number" min="1e-15" step={isResistor?'100':'0.000001'} value={draftValues[component.id] ?? String(component.value.magnitude)} onChange={(e)=>{const v=e.target.value;setDraftValues({...draftValues,[component.id]:v});if(v.trim()&&Number.isFinite(Number(v))&&Number(v)>0)updateMagnitude(component.id,Number(v));}} onBlur={()=>setDraftValues({...draftValues,[component.id]:String(circuit?.components.find(c=>c.id===component.id)?.value.magnitude??component.value.magnitude)})}/></div>})}
            <button className="run-button" onClick={()=>run()} disabled={!circuit||busy}><Play size={17} fill="currentColor"/>{busy?'Simulating with ngspice…':'Run simulation'}</button><p className="microcopy">Values are in SI units: Ω, F, V. The netlist is generated from this edited model.</p>
          </section>
          <section className="panel explanation-panel"><div className="eyebrow">04 / GEMMA 4 EXPLANATION</div><h2>AI circuit tutor</h2><p>Explanations use a fresh server-side ngspice run. Facts, textbook calculations, assumptions and hypotheses are separated.</p><textarea className="question-input" value={question} onChange={(e)=>setQuestion(e.target.value)} aria-label="Ask Gemma a circuit question"/><button className="secondary-button explain-button" onClick={askGemma} disabled={!health?.gemma_available||result?.status!=='success'||explaining}>{explaining?'Asking Gemma…':'Ask Gemma about this result'}</button>{!health?.gemma_available&&<div className="unavailable"><Cpu size={17}/><span>Ollama/model unavailable · run <code>ollama run gemma4:e2b</code> and restart the backend.</span></div>}{explanation&&<div className="explanation-result"><b>{explanation.circuit_summary}</b><p>{explanation.physics_explanation}</p>{[['Measured from ngspice',explanation.measured_facts],['Theory',explanation.theoretical_calculations],['Assumptions',explanation.assumptions],['Hypotheses',explanation.hypotheses],['Try next',explanation.suggested_experiments]].map(([title,items])=>(items as string[]).length>0&&<div key={title as string}><strong>{title as string}</strong><ul>{(items as string[]).map((item,i)=><li key={i}>{item}</li>)}</ul></div>)}</div>}</section>
          <div className="safety-note"><AlertTriangle size={15}/><span>Educational prototype. Not a certified electrical safety or professional EDA tool.</span></div>
        </aside>
      </section>
    </main>
    <footer> CIRCUITLENS <span>·</span> REAL SIMULATION, CLEAR EXPLANATION</footer>
  </div>;
}
