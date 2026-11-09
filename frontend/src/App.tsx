import { useEffect, useMemo, useRef, useState } from 'react';
import { ArrowUpRight, ArrowLeft, ArrowRight, RotateCcw, Activity, AlertTriangle, CircuitBoard, Cpu, FileImage, FlaskConical, Play, Upload } from 'lucide-react';
import { analyzeImage, explainSimulation, fetchHealth, fetchSeededCircuit, simulateCircuit, validateCircuit } from './api/client';
import type { CircuitModel, GroundedExplanation, ImageAnalysisResult, ImageCandidate, SimulationResult, WaveformTrace } from './types/circuit';

type View = 'home' | 'circuit' | 'results' | 'tutor';
const views: View[] = ['home', 'circuit', 'results', 'tutor'];
const viewLabels = ['Overview', 'Your circuit', 'Simulation', 'AI tutor'];

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
  const [view, setView] = useState<View>('home');
  const headingRef = useRef<HTMLHeadingElement>(null);
  const [checking, setChecking] = useState(false);
  function navigate(next: View) { setView(next); }
  useEffect(() => { headingRef.current?.focus({ preventScroll: true }); }, [view]);
  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      const target = event.target as HTMLElement;
      if (target.closest('input, textarea, select, [contenteditable="true"]') || event.ctrlKey || event.metaKey || event.altKey) return;
      const index = Number(event.key) - 1;
      if (index >= 0 && index < views.length) { event.preventDefault(); setView(views[index]); }
    }
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, []);
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

  useEffect(() => () => { if (image) URL.revokeObjectURL(image); }, [image]);
  async function refreshHealth() {
    setChecking(true);
    try { setHealth(await fetchHealth()); }
    catch { setHealth(null); setError('Backend is not connected. Start the backend and reconnect.'); }
    finally { setChecking(false); }
  }
  async function resetExample() {
    try {
      const seed = await fetchSeededCircuit();
      setCircuit(seed); setDraftValues({}); setImage(''); setImageFile(null); setImageName('');
      setAnalysis(null); setReviewCandidates([]); setTopologyConfirmed(false); setExplanation(null);
      setError(''); navigate('circuit'); await run(seed);
    } catch (e) { setError(e instanceof Error ? e.message : 'Could not load example.'); }
  }
  async function run(current = circuit) {
    if (!current) return;
    setBusy(true); setError(''); setResult(null); setExplanation(null);
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
      setCircuit(verdict.normalized_circuit || candidate); setDraftValues({}); setResult(null); setExplanation(null); setError('');
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
    setResult(null); setExplanation(null);
  }
  const resistor = circuit?.components.find((c) => c.type === 'resistor');
  const capacitor = circuit?.components.find((c) => c.type === 'capacitor');
  const tauMs = useMemo(() => resistor && capacitor ? resistor.value.magnitude * capacitor.value.magnitude * 1000 : 0, [resistor, capacitor]);
  const out = result?.traces.find((trace) => trace.name.toLowerCase() === 'v(out)') || result?.traces[0];

  return <div className="app-shell" data-view={view}>
    <a className="skip-link" href="#workspace">Skip to workspace</a>
    <header className="topbar">
      <a className="brand" href="#" onClick={(e) => { e.preventDefault(); navigate('home'); }}><CircuitBoard size={22}/> <span>CIRCUITLENS<span className="brand-tag"> / PERSONAL ELECTRONICS LAB</span></span></a>
      <div className="hardware-label">CL—001 <span>EST. 2026</span></div>
    </header>
    <div className="terminal-frame">
    <div className="terminal-bar"><span><i className={`dot ${health ? 'green' : ''}`}/> LOCAL WORKSPACE</span><span>{String(views.indexOf(view)+1).padStart(2,'0')} / {viewLabels[views.indexOf(view)].toUpperCase()}</span><button onClick={refreshHealth} disabled={checking} title="Recheck backend and model connection"><RotateCcw size={12}/>{checking?'CONNECTING…':health?'CONNECTED':'RECONNECT'}</button></div>
    <main id="workspace" className="terminal-screen">
      <nav className="section-nav" aria-label="Workspace sections">{views.map((item,index)=><button key={item} aria-current={view===item?'page':undefined} onClick={()=>navigate(item)}><span>0{index+1}</span>{viewLabels[index]}</button>)}</nav>
      <section className="home-view" hidden={view!=='home'}>
        <div className="hero-meta"><span>VISION × SIMULATION × UNDERSTANDING</span><span>AN INTERACTIVE CIRCUIT COMPANION</span></div>
        <div className="hero-grid">
          <div className="hero-intro"><h1 ref={view==='home'?headingRef:undefined} tabIndex={-1} className="hero-title">CIRCUIT<br/><span>LENS</span><span className="title-period">.</span></h1>
            <div className="hero-bottom"><div><p className="hero-kicker">A LITTLE CURIOSITY.<br/>A LOT OF CONNECTIONS.</p><p className="hero-description">From a sketch to a signal.<br/>Explore your circuit, see the physics,<br/>and make sense of every component.</p><button className="text-link" onClick={()=>navigate('circuit')}>Enter the lab <ArrowUpRight size={21}/></button></div>
            <div className="signal-art" aria-hidden="true"><svg viewBox="0 0 240 240"><defs><pattern id="signal-grid" width="20" height="20" patternUnits="userSpaceOnUse"><path d="M20 0H0V20" fill="none" stroke="currentColor" strokeOpacity=".16"/></pattern></defs><circle cx="120" cy="120" r="106" fill="url(#signal-grid)"/><circle cx="120" cy="120" r="106" fill="none" stroke="currentColor"/><circle cx="120" cy="120" r="82" fill="none" stroke="currentColor" strokeDasharray="1 7"/><path d="M8 120H232M120 8V232" stroke="currentColor" strokeOpacity=".3"/><path className="signal-wave" d="M20 120H48L67 120L81 67L103 173L122 96L138 138L151 120H220" fill="none" stroke="currentColor" strokeWidth="4"/><circle cx="220" cy="120" r="5" fill="currentColor"/></svg><span>FOLLOW THE SIGNAL ↗</span></div></div>
          </div>
          <div className="directory"><div className="directory-heading"><span>// YOUR NEXT EXPERIMENT</span><span>↓</span></div>
            {[['circuit','Build & inspect','Upload a schematic or start with our RC circuit.'],['results','Follow the signal','Real waveforms. Real circuit simulation.'],['tutor','Ask a better question','Explore the why with your Gemma circuit tutor.']].map(([key,title,description],index)=><button className="directory-item" key={key} onClick={()=>navigate(key as View)}><span className="directory-number">0{index+1}</span><span><strong>{title}</strong><small>{description}</small></span><ArrowUpRight/></button>)}
            <div className="connection-card"><span className="eyebrow">ON YOUR WORKBENCH</span><div><i className={`dot ${health?.ngspice_available?'green':''}`}/><span>ngspice simulator</span><b>{health?.ngspice_available?'READY':'OFFLINE'}</b></div><div><i className={`dot ${health?.gemma_available?'green':''}`}/><span>Gemma 4 vision + tutor</span><b>{health?.gemma_available?'READY':'OFFLINE'}</b></div><p>Runs locally. Built for experimenting.</p></div>
          </div>
        </div>
      </section>
      <div className="page-heading" hidden={view==='home'}><div><div className="eyebrow">THE WORKBENCH / {view.toUpperCase()}</div><h1 ref={view!=='home'?headingRef:undefined} tabIndex={-1}>{view==='circuit'?'Make connections.':view==='results'?'See what happens.':'Understand the why.'}</h1><p>{view==='circuit'?'Start with an example, or bring your own schematic.':view==='results'?'Every point on this curve comes from your circuit simulation.':'A curious question is the beginning of a good experiment.'}</p></div><button className="secondary-button" onClick={resetExample}><RotateCcw size={15}/> Reset RC example</button></div>
      {error && <div className="notice error" role="alert"><AlertTriangle size={18}/><span>{error}</span></div>}
      <section className="work-grid" aria-label="Circuit workbench" hidden={view==='home'}>
        <div className="main-column">
          <section className="panel circuit-panel"><div className="panel-header"><div><div className="eyebrow">01 / CIRCUIT INPUT</div><h2>{imageName || circuit?.name || 'Seeded RC charge'}</h2></div><div className="header-actions"><label className="secondary-button upload-button"><Upload size={16}/> Choose PNG/JPG<input type="file" accept="image/png,image/jpeg" onChange={(e) => { const file=e.target.files?.[0]; if(file){ if(file.size>10*1024*1024){setError('Image must be smaller than 10 MB.');return;} setImage(URL.createObjectURL(file)); setImageFile(file); setImageName(file.name); setAnalysis(null); setReviewCandidates([]); setTopologyConfirmed(false); } }}/></label><button className="secondary-button" onClick={analyzeSelectedImage} disabled={!imageFile||analyzing||!health?.gemma_available}>{analyzing?'Analyzing…':'Analyze with Gemma'}</button></div></div>
            {image ? <div className="image-preview"><img src={image} alt={`Uploaded schematic preview: ${imageName}`}/><div><FileImage size={16}/>{analysis?`Gemma candidates · ${analysis.components.length} component(s) · review required`:'Choose Analyze with Gemma to inspect this schematic.'}</div></div> : <div className="schematic" aria-label="Seeded RC circuit diagram"><svg viewBox="0 0 760 210" role="img" aria-label="5 volt source, resistor, capacitor to ground"><path d="M100 125V65H220M340 65H520V105M520 130V175H100V155M520 175V185"/><path d="M220 65l10 -12 18 24 18 -24 18 24 18 -24 18 12H340M495 105H545M495 130H545M504 185H536M510 192H530M516 199H524"/><circle cx="100" cy="140" r="15"/><path d="M100 130V140M95 135H105M95 147H105"/><circle cx="520" cy="65" r="4"/><text x="40" y="115">V1 · 5 V</text><text x="240" y="38">R1 · {resistor ? resistor.value.magnitude/1000 : 1} kΩ</text><text x="540" y="70">Vout</text><text x="555" y="125">C1 · {capacitor ? Number((capacitor.value.magnitude*1e6).toPrecision(5)) : 10} μF</text><text x="555" y="180">GND</text></svg><div className="schematic-caption"><span><i className="legend-line"/>Confirmed seeded connectivity</span><span>5 V step · capacitor starts at 0 V</span></div></div>}
          </section>
          {analysis && <section className="panel review-panel"><div className="eyebrow">IMAGE INTERPRETATION / USER REVIEW REQUIRED</div><h2>Candidate components</h2><p className="muted">Gemma's visual confidence is not a calibrated probability. Correct values and both terminal nodes; use node 0 for ground connections.</p>{reviewCandidates.map((item,index)=><div className="review-row" key={`${index}-${item.id}`}><label className="review-check"><input aria-label={`Confirm ${item.id}`} type="checkbox" checked={item.confirmed} onChange={(e)=>setReviewCandidates(reviewCandidates.map((c,i)=>i===index?{...c,confirmed:e.target.checked}:c))}/></label><div className="review-main"><div className="review-fields"><input aria-label="Component ID" value={item.id} onChange={(e)=>setReviewCandidates(reviewCandidates.map((c,i)=>i===index?{...c,id:e.target.value}:c))}/><strong>{item.type.replace(/_/g,' ')}</strong></div><small>{item.visual_evidence||'No visual evidence returned'} · model estimate {(item.confidence*100).toFixed(0)}%</small><div className="review-fields"><input aria-label={`${item.id} value`} placeholder="SI value" value={item.valueDraft} onChange={(e)=>setReviewCandidates(reviewCandidates.map((c,i)=>i===index?{...c,valueDraft:e.target.value}:c))}/><input aria-label={`${item.id} unit`} placeholder="unit" value={item.unitDraft} onChange={(e)=>setReviewCandidates(reviewCandidates.map((c,i)=>i===index?{...c,unitDraft:e.target.value}:c))}/><input aria-label={`${item.id} terminal nodes`} placeholder="node1, node2" value={item.nodesDraft} onChange={(e)=>setReviewCandidates(reviewCandidates.map((c,i)=>i===index?{...c,nodesDraft:e.target.value}:c))}/></div></div></div>)}<div className="review-warnings">{analysis.observed_text.length>0&&<p><b>Text read:</b> {analysis.observed_text.join(' · ')}</p>}{analysis.ambiguities.map((a,i)=><p key={`a${i}`}><AlertTriangle size={13}/>{a}</p>)}{analysis.unsupported_symbols.map((a,i)=><p key={`u${i}`}>Unsupported symbol: {a}</p>)}<p>{analysis.line_segments.length} line segment hint(s) from image geometry. Crossings do not imply a connection.</p></div><label className="acknowledge"><input type="checkbox" checked={topologyConfirmed} onChange={(e)=>setTopologyConfirmed(e.target.checked)}/> I reviewed the component values, every terminal-node assignment, and the marked crossings.</label><button className="run-button" onClick={applyReviewedCircuit}>Apply reviewed circuit</button><p className="microcopy">Applying still requires backend electrical validation. The simulator will reject any model that retains ambiguity flags.</p></section>}
          <section className="panel results-panel" aria-busy={busy}><div className="panel-header"><div><div className="eyebrow">03 / SIMULATION</div><h2>Transient response</h2></div>{result?.status==='success' && <span className="result-badge"><span className="dot green"/> SIMULATED</span>}</div><div className="chart-wrap"><div className="chart-title"><span>Output node <b>V(out)</b></span><span>Voltage <b>V</b></span></div>{busy?<div className="chart-empty" role="status"><Activity size={24}/>Running your circuit…</div>:<Waveform trace={out}/>}</div>
            <div className="metrics"><div><span>TIME CONSTANT</span><strong>{tauMs.toFixed(2)} <small>ms</small></strong><em>R × C</em></div><div><span>FINAL OUTPUT</span><strong>{result?.status==='success' && result.summary.final_voltage !== undefined ? `${result.summary.final_voltage.toFixed(3)} V` : '—'}</strong><em>from ngspice samples</em></div><div><span>SAMPLES</span><strong>{result?.status==='success' ? result.summary.num_time_points ?? '—' : '—'}</strong><em>actual parsed data points</em></div></div>
            {result?.theory_verification && <div className={`notice ${result.theory_verification.passed_tolerance?'success':'warn'}`}><FlaskConical size={17}/><span>RC check: {result.theory_verification.explanation} Tolerance {result.theory_verification.tolerance_percent}%.</span></div>}
            {result?.status==='unavailable' && <div className="notice warn"><AlertTriangle size={17}/><span>ngspice is unavailable. No simulated waveform is shown.</span></div>}
            {result?.status==='error' && <div className="notice error"><AlertTriangle size={17}/><span>{result.error_message || 'ngspice did not return usable simulation data.'} No waveform is shown.</span></div>}
          </section>
        </div>
        <aside className="side-column"><section className="panel editor-panel"><div className="eyebrow">02 / MODEL EDITOR</div><h2>Components</h2><p className="muted">Change a value, then run the circuit again.</p>
            {circuit?.components.filter((c)=>c.type==='voltage_source_dc').map((component)=><div className="component-row" key={component.id}><div className="component-icon source">V</div><div className="component-meta"><strong>{component.id} <span>DC source</span></strong><small>{component.terminals.join(' → ')}</small></div><div className="component-value">{component.value.magnitude} V</div></div>)}
            {circuit?.components.filter((c)=>c.type==='resistor'||c.type==='capacitor').map((component)=>{const isResistor=component.type==='resistor';return <div className="component-row" key={component.id}><div className={`component-icon ${isResistor?'resistor':'capacitor'}`}>{isResistor?'R':'C'}</div><div className="component-meta"><strong>{component.id} <span>{isResistor?'Resistor':'Capacitor'}</span></strong><small>{component.terminals.join(' → ')}</small></div><input className="value-input" aria-label={`${component.id} SI value`} type="number" min="1e-15" step={isResistor?'100':'0.000001'} value={draftValues[component.id] ?? String(component.value.magnitude)} onChange={(e)=>{const v=e.target.value;setDraftValues({...draftValues,[component.id]:v});if(v.trim()&&Number.isFinite(Number(v))&&Number(v)>0)updateMagnitude(component.id,Number(v));}} onBlur={()=>setDraftValues({...draftValues,[component.id]:String(circuit?.components.find(c=>c.id===component.id)?.value.magnitude??component.value.magnitude)})}/></div>})}
            <button className="run-button" onClick={()=>{ navigate('results'); run(); }} disabled={!circuit||busy}><Play size={17} fill="currentColor"/>{busy?'Simulating with ngspice…':'Run simulation'}</button><p className="microcopy">Values are in SI units: Ω, F, V. The netlist is generated from this edited model.</p>
          </section>
          <section className="panel explanation-panel"><div className="eyebrow">04 / GEMMA 4 EXPLANATION</div><h2>Let’s work it out.</h2><p>Ask about your circuit, its waveform, or what would happen if you changed a component.</p>{result?.status!=='success'&&<div className="tutor-prerequisite">Start with a successful simulation so Gemma has results to explain.<button className="text-link" onClick={()=>navigate('circuit')}>Go to your circuit <ArrowRight size={16}/></button></div>}<textarea className="question-input" value={question} onChange={(e)=>setQuestion(e.target.value)} aria-label="Ask Gemma a circuit question"/><button className="secondary-button explain-button" onClick={askGemma} disabled={!health?.gemma_available||result?.status!=='success'||explaining}>{explaining?'Asking Gemma…':'Ask Gemma about this result'}</button>{!health?.gemma_available&&<div className="unavailable"><Cpu size={17}/><span>Ollama/model unavailable · run <code>ollama run gemma4:e2b</code> and restart the backend.</span></div>}{explanation&&<div className="explanation-result"><b>{explanation.circuit_summary}</b><p>{explanation.physics_explanation}</p>{[['Measured from ngspice',explanation.measured_facts],['Theory',explanation.theoretical_calculations],['Assumptions',explanation.assumptions],['Hypotheses',explanation.hypotheses],['Try next',explanation.suggested_experiments]].map(([title,items])=>(items as string[]).length>0&&<div key={title as string}><strong>{title as string}</strong><ul>{(items as string[]).map((item,i)=><li key={i}>{item}</li>)}</ul></div>)}</div>}</section>
          <div className="safety-note"><AlertTriangle size={15}/><span>Educational prototype. Not a certified electrical safety or professional EDA tool.</span></div>
        </aside>
      </section>
    </main>
    <div className="screen-foot"><span><kbd>1</kbd>–<kbd>4</kbd> SWITCH SECTIONS</span><span>REAL SIMULATION. HUMAN CURIOSITY.</span><span>CL / 001</span></div>
    </div>
    <footer className="console-controls"><span className="console-caption">A SPACE TO<br/><b>FIGURE THINGS OUT.</b></span><div><button onClick={()=>navigate('home')}><CircuitBoard size={15}/> HOME</button><button onClick={()=>navigate(views[(views.indexOf(view)+3)%4])}><ArrowLeft size={15}/> BACK</button><button onClick={()=>navigate(views[(views.indexOf(view)+1)%4])}>NEXT <ArrowRight size={15}/></button><button className="console-primary" onClick={()=>{navigate('results');run();}} disabled={!circuit||busy}><Play size={14}/>{busy?'RUNNING…':'RUN CIRCUIT'}</button></div><span className="console-caption">DESIGNED FOR<br/><b>THE CURIOUS MIND.</b></span></footer>
  </div>;
}
