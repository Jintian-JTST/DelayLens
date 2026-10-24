import { useEffect, useRef, useState, type FormEvent } from "react";
import {
  api,
  ApiError,
  type CurveRequest,
  type CurveResponse,
  type Interpretation,
  type Route,
} from "./api";
import { recommend, delayedPoint, MIN_RECOMMENDATION_TRIPS } from "./advisor";
import { demoCurve, demoRoutes } from "./demo";
import { demoRequested } from "./demoFlag";
import { nextResultFocus } from "./resultFocus";
import { exampleDeadline, isCovered, pickInitialRoute } from "./defaults";
import {
  askOffNotice,
  nextAskOffReason,
  type AskOffReason,
} from "./askAvailability";
import {
  browserZone,
  inputDate,
  inputISO,
  timeLabel,
  zoneFor,
  type Clock,
} from "./time";
import DepartureCurve from "./components/DepartureCurve";
import Icon from "./components/Icon";
import LivePanel from "./components/LivePanel";
import { isOfflineSnapshot } from "./live";
import Methodology from "./components/Methodology";

const ACCESS_CODE_KEY = "delaylens.askAccessCode";

interface JourneyForm {
  routeId: string;
  deadline: string;
  walkTo: number;
  walkFrom: number;
}
interface Result {
  curve: CurveResponse;
  request: CurveRequest;
  route: Route;
}
const defaultDeadline = () =>
  new Date(
    Math.ceil((Date.now() + 90 * 60_000) / 1_800_000) * 1_800_000,
  ).toISOString();
const formFor = (routeId: string, clock: Clock): JourneyForm => ({
  routeId,
  deadline: inputDate(defaultDeadline(), clock),
  walkTo: 5,
  walkFrom: 5,
});
const requestFor = (
  form: JourneyForm,
  tolerance: number,
  clock: Clock,
): CurveRequest => ({
  route_id: form.routeId,
  deadline: inputISO(form.deadline, clock),
  walk_to_min: form.walkTo,
  walk_from_min: form.walkFrom,
  tolerance: tolerance / 100,
  window_min: 90,
});

export default function App() {
  const [mode, setMode] = useState<"api" | "demo">("api");
  const [demoFlag] = useState(() =>
    demoRequested(window.location.search, window.location.hash),
  );
  const [tab, setTab] = useState<"plan" | "method">("plan");
  const [clock, setClock] = useState<Clock>("local");
  const clockRef = useRef(clock);
  clockRef.current = clock;
  const [routes, setRoutes] = useState<Route[]>([]);
  const [catalogBusy, setCatalogBusy] = useState(true);
  const [catalogError, setCatalogError] = useState("");
  const [retry, setRetry] = useState(0);
  const [form, setForm] = useState<JourneyForm>(() => formFor("", "local"));
  const [tolerance, setTolerance] = useState(10);
  const toleranceRef = useRef(tolerance);
  toleranceRef.current = tolerance;
  const [conservative, setConservative] = useState(false);
  const [delay, setDelay] = useState(0);
  const [result, setResult] = useState<Result | null>(null);
  const [curveBusy, setCurveBusy] = useState(false);
  const [curveError, setCurveError] = useState("");
  const [question, setQuestion] = useState("");
  const [askBusy, setAskBusy] = useState(false);
  const [askMessage, setAskMessage] = useState("");
  // Team passcode for Ask on the public site; kept for this browser tab only.
  const [accessCode, setAccessCode] = useState(() => {
    try {
      return sessionStorage.getItem(ACCESS_CODE_KEY) ?? "";
    } catch {
      return "";
    }
  });
  const [needsCode, setNeedsCode] = useState(false);
  const [askOff, setAskOff] = useState<AskOffReason>(null);
  const [interpretation, setInterpretation] = useState<Interpretation | null>(
    null,
  );
  const curveController = useRef<AbortController | null>(null);
  const askController = useRef<AbortController | null>(null);
  const adviceRef = useRef<HTMLElement | null>(null);
  const focusResultPending = useRef(false);

  useEffect(() => {
    const controller = new AbortController();
    curveController.current?.abort();
    askController.current?.abort();
    curveController.current = controller;
    setRoutes([]);
    setResult(null);
    setCatalogBusy(true);
    setCatalogError("");
    setCurveError("");
    setAskMessage("");
    setInterpretation(null);
    setAskBusy(false);
    setAskOff(null);
    setDelay(0);
    void (async () => {
      try {
        const list =
          mode === "demo" ? demoRoutes : await api.routes(controller.signal);
        if (controller.signal.aborted) return;
        setRoutes(list);
        setCatalogBusy(false);
        if (!list.length) {
          setCurveBusy(false);
          return;
        }
        const initialRoute = pickInitialRoute(list)!;
        const initialForm = formFor(initialRoute.route_id, clockRef.current);
        const example = exampleDeadline(initialRoute);
        if (example && !isCovered(initialRoute, defaultDeadline()))
          initialForm.deadline = inputDate(example, clockRef.current);
        setForm(initialForm);
        setCurveBusy(true);
        const body = requestFor(
          initialForm,
          toleranceRef.current,
          clockRef.current,
        );
        try {
          const curve =
            mode === "demo"
              ? demoCurve(body)
              : await api.curve(body, controller.signal);
          if (!controller.signal.aborted)
            setResult({ curve, request: body, route: initialRoute });
        } catch {
          if (!controller.signal.aborted)
            setCurveError(
              "The departure curve could not be loaded. Check your journey and try again.",
            );
        } finally {
          if (!controller.signal.aborted) setCurveBusy(false);
        }
      } catch {
        if (!controller.signal.aborted) {
          setCatalogError(
            "We couldn’t connect to the journey service. You can retry or explore a labelled demo.",
          );
          setCatalogBusy(false);
          setCurveBusy(false);
        }
      }
    })();
    return () => {
      controller.abort();
      curveController.current?.abort();
      askController.current?.abort();
    };
  }, [mode, retry]);

  // Snapshot mode is known from the first curve basis, before any question.
  useEffect(() => {
    if (result)
      setAskOff((current) =>
        nextAskOffReason(current, { basis: result.curve.data_quality.basis }),
      );
  }, [result]);

  // The old result unmounts on submit, which drops focus to the page top;
  // hand it to the new recommendation once for keyboard and screen-reader users.
  useEffect(() => {
    const next = nextResultFocus(focusResultPending.current, !!result);
    focusResultPending.current = next.pending;
    if (next.focus) adviceRef.current?.focus();
  }, [result]);

  const demo = mode === "demo";
  const fixture =
    demo ||
    routes.some((route) => route.line_id === "fixture") ||
    /fixture/i.test(result?.curve.data_quality.basis ?? "");
  const points =
    result?.curve.data_quality.status === "insufficient_data"
      ? []
      : (result?.curve.points ?? []);
  const best = recommend(points, tolerance / 100, conservative);
  const lowData = result?.curve.data_quality.status === "low_data";
  const hasEligibleDepartures = points.some(
    (point) => point.n_trips >= MIN_RECOMMENDATION_TRIPS,
  );
  const selected = best ? delayedPoint(points, best, delay) : null;
  const activeRoute = routes.find((route) => route.route_id === form.routeId);
  const exampleIso = activeRoute ? exampleDeadline(activeRoute) : null;
  const latestCoveredHour = activeRoute?.hours_covered.length
    ? Math.max(...activeRoute.hours_covered.map(Date.parse))
    : null;
  const zone = zoneFor(clock);
  const dirty =
    !!result &&
    (form.routeId !== result.request.route_id ||
      form.walkTo !== result.request.walk_to_min ||
      form.walkFrom !== result.request.walk_from_min ||
      form.deadline !== inputDate(result.request.deadline, clock));

  function editForm(patch: Partial<JourneyForm>) {
    askController.current?.abort();
    setAskBusy(false);
    setInterpretation(null);
    setForm((current) => ({ ...current, ...patch }));
  }

  async function submitJourney(event: FormEvent) {
    event.preventDefault();
    if (!activeRoute) return;
    focusResultPending.current = true;
    askController.current?.abort();
    setAskBusy(false);
    setAskMessage("");
    setInterpretation(null);
    curveController.current?.abort();
    const controller = new AbortController();
    curveController.current = controller;
    setCurveBusy(true);
    setCurveError("");
    setResult(null);
    setDelay(0);
    try {
      const body = requestFor(form, tolerance, clock);
      const curve = demo
        ? demoCurve(body)
        : await api.curve(body, controller.signal);
      if (!controller.signal.aborted)
        setResult({ curve, request: body, route: activeRoute });
    } catch {
      if (!controller.signal.aborted)
        setCurveError(
          "We couldn’t calculate this journey. Check the deadline and try again.",
        );
    } finally {
      if (!controller.signal.aborted) setCurveBusy(false);
    }
  }

  async function submitQuestion(event: FormEvent) {
    event.preventDefault();
    if (!question.trim() || demo || askOff) return;
    askController.current?.abort();
    const controller = new AbortController();
    askController.current = controller;
    setAskBusy(true);
    setAskMessage("");
    setInterpretation(null);
    try {
      const response = await api.ask(
        question.trim(),
        controller.signal,
        accessCode,
      );
      if (controller.signal.aborted) return;
      setNeedsCode(false);
      setAskOff((current) =>
        nextAskOffReason(current, { askStatus: response.status }),
      );
      // The Ask-off notice explains this case; skip the duplicate reply.
      if (response.status === "gemini_unavailable") return;
      setAskMessage(response.answer);
      const interpreted = response.interpretation;
      setInterpretation(interpreted);
      const route = routes.find((r) => r.route_id === interpreted.route_id);
      const hasDeadline =
        !!interpreted.deadline &&
        Number.isFinite(Date.parse(interpreted.deadline));
      // Keep usable partial parsing when Gemini cannot complete a request.
      setForm((current) => ({
        ...current,
        ...(route ? { routeId: route.route_id } : {}),
        ...(hasDeadline
          ? { deadline: inputDate(interpreted.deadline!, clock) }
          : {}),
        ...(interpreted.walk_to_min != null
          ? { walkTo: interpreted.walk_to_min }
          : {}),
        ...(interpreted.walk_from_min != null
          ? { walkFrom: interpreted.walk_from_min }
          : {}),
      }));
      if (interpreted.tolerance != null)
        setTolerance(interpreted.tolerance * 100);
      if (
        route &&
        interpreted.deadline &&
        Number.isFinite(Date.parse(interpreted.deadline))
      ) {
        const next = {
          routeId: route.route_id,
          deadline: inputDate(interpreted.deadline, clock),
          walkTo: interpreted.walk_to_min ?? form.walkTo,
          walkFrom: interpreted.walk_from_min ?? form.walkFrom,
        };
        setForm(next);
        const risk = (interpreted.tolerance ?? tolerance / 100) * 100;
        setTolerance(risk);
        setDelay(0);
        if (response.status === "ok" && response.curve) {
          curveController.current?.abort();
          setCurveBusy(false);
          setCurveError("");
          setResult({
            curve: response.curve,
            route,
            request: requestFor(next, risk, clock),
          });
        }
      }
    } catch (error) {
      if (controller.signal.aborted) return;
      if (error instanceof ApiError && error.status === 401) {
        setNeedsCode(true);
        setAskMessage(
          accessCode
            ? "That team passcode was not accepted. The journey form below works for everyone."
            : "Ask DelayLens is limited to the DelayLens team on this site. Enter the team passcode to use it; the journey form below works for everyone.",
        );
      } else {
        setAskMessage(
          "Ask DelayLens is unavailable right now. Your journey form still works.",
        );
      }
    } finally {
      if (!controller.signal.aborted) setAskBusy(false);
    }
  }

  function changeClock(next: Clock) {
    askController.current?.abort();
    setAskBusy(false);
    let nextDeadline = form.deadline;
    try {
      nextDeadline = inputDate(inputISO(form.deadline, clock), next);
    } catch {
      /* An incomplete datetime stays editable. */
    }
    setForm((current) => ({ ...current, deadline: nextDeadline }));
    setClock(next);
  }

  return (
    <div className="app-shell">
      <a className="skip-link" href="#main">
        Skip to journey planner
      </a>
      <header className="site-header">
        <a
          className="brand"
          href="#main"
          aria-label="DelayLens home"
          onClick={() => setTab("plan")}
        >
          <span className="brand-mark">
            d<span>l</span>
          </span>
          <span>
            delay<span className="brand-light">lens</span>
            <sup>BETA</sup>
          </span>
        </a>
        <nav aria-label="Main navigation">
          <button
            type="button"
            className={tab === "plan" ? "nav-link active" : "nav-link"}
            aria-current={tab === "plan" ? "page" : undefined}
            onClick={() => setTab("plan")}
          >
            Journey planner
          </button>
          <button
            type="button"
            className={tab === "method" ? "nav-link active" : "nav-link"}
            aria-current={tab === "method" ? "page" : undefined}
            onClick={() => setTab("method")}
          >
            Our methodology
          </button>
          {(demoFlag || demo) && (
            <button
              type="button"
              className="nav-link"
              aria-label={demo ? "Use real route data" : "Try labelled demo"}
              onClick={() => {
                setTab("plan");
                setMode(demo ? "api" : "demo");
              }}
            >
              {demo ? "Real routes" : "Try demo"}
            </button>
          )}
        </nav>
        <div className="header-right">
          <span className="region">LONDON, UK</span>
          <span className={`badge ${fixture ? "badge-amber" : ""}`}>
            <span className="status-dot" />
            {catalogBusy
              ? "Connecting"
              : fixture
                ? "Fixture data"
                : catalogError
                  ? "Service offline"
                  : routes.length
                    ? isOfflineSnapshot(result?.curve.data_quality.basis)
                      ? "Offline snapshot"
                      : "Service connected"
                    : "No routes yet"}
          </span>
        </div>
      </header>
      <main id="main">
        <section className="intro">
          <div>
            <div className="eyebrow">
              <span className="tiny-route" />
              LESS GUESSWORK. MORE GETTING THERE.
            </div>
            <h1>
              A better time to <em>leave.</em>
            </h1>
            <p>
              Your deadline. Your comfort with risk. A clearer way to get there.
            </p>
          </div>
          <div className="intro-note">
            <Icon name="shield" size={25} />
            <span>
              Know the odds.
              <br />
              <strong>Make the call.</strong>
            </span>
          </div>
        </section>
        {fixture && (
          <div className="fixture-banner" role="status">
            <Icon name="info" size={17} />
            <span>
              <strong>{demo ? "Interactive demo" : "Backend fixture"}.</strong>{" "}
              Probabilities and sample counts are synthetic. This is not travel
              advice.
            </span>
            {demo && (
              <button type="button" onClick={() => setMode("api")}>
                Use journey service <Icon name="arrow" size={16} />
              </button>
            )}
          </div>
        )}
        {tab === "method" ? (
          <Methodology routes={routes} demo={fixture} clock={clock} />
        ) : (
          <>
            <section className="ask-bar" aria-label="Ask DelayLens">
              <div className="ask-label">
                <span className="spark-icon">
                  <Icon name="spark" size={20} />
                </span>
                <div>
                  <strong>Ask DelayLens</strong>
                  <span>Or put it in your own words.</span>
                </div>
              </div>
              <form onSubmit={submitQuestion}>
                <label className="sr-only" htmlFor="question">
                  Describe your journey
                </label>
                <input
                  id="question"
                  value={question}
                  onChange={(event) => setQuestion(event.target.value)}
                  placeholder={
                    askOff
                      ? "Ask is unavailable"
                      : "“I need to be at Oxford Circus around 2…”"
                  }
                  maxLength={500}
                  required
                  disabled={demo || !routes.length || askBusy || !!askOff}
                />
                {needsCode && (
                  <>
                    <label className="sr-only" htmlFor="ask-passcode">
                      Team passcode
                    </label>
                    <input
                      id="ask-passcode"
                      className="ask-passcode"
                      type="password"
                      autoComplete="off"
                      placeholder="Team passcode"
                      value={accessCode}
                      onChange={(event) => {
                        const next = event.target.value;
                        setAccessCode(next);
                        try {
                          sessionStorage.setItem(ACCESS_CODE_KEY, next);
                        } catch {
                          // Storage can be unavailable; the code still works for this page.
                        }
                      }}
                      disabled={askBusy}
                    />
                  </>
                )}
                <button
                  className="ask-button"
                  type="submit"
                  disabled={
                    demo ||
                    !routes.length ||
                    askBusy ||
                    !!askOff ||
                    !question.trim()
                  }
                >
                  {askBusy ? "Thinking…" : "Ask"}
                  <Icon name="arrow" size={17} />
                </button>
              </form>
            </section>
            {askOff && !demo && (
              <p className="demo-ask-note" role="status">
                {askOffNotice(askOff)}
                {askOff === "gemini" && (
                  <>
                    {" "}
                    <button
                      type="button"
                      className="text-button"
                      onClick={() => setAskOff(null)}
                    >
                      Try Ask again
                    </button>
                  </>
                )}
              </p>
            )}
            {askMessage && (
              <div className="ask-message" role="status">
                <Icon name="spark" size={18} />
                <span>
                  {askMessage}{" "}
                  <a href="#journey-form">
                    Edit the interpretation in the form below.
                  </a>
                </span>
              </div>
            )}
            {interpretation && (
              <div
                className="interpretation-chips"
                aria-label="Editable interpretation"
              >
                <span>UNDERSTOOD AS</span>
                {interpretation.route_id &&
                  routes.some(
                    (r) => r.route_id === interpretation.route_id,
                  ) && (
                    <button
                      type="button"
                      onClick={() => document.getElementById("route")?.focus()}
                    >
                      Route ·{" "}
                      {
                        routes.find(
                          (r) => r.route_id === interpretation.route_id,
                        )!.destination.name
                      }{" "}
                      <span>Edit</span>
                    </button>
                  )}
                {interpretation.deadline &&
                  Number.isFinite(Date.parse(interpretation.deadline)) && (
                    <button
                      type="button"
                      onClick={() =>
                        document.getElementById("deadline")?.focus()
                      }
                    >
                      Arrive by · {timeLabel(interpretation.deadline, clock)}{" "}
                      <span>Edit</span>
                    </button>
                  )}
                {interpretation.tolerance != null && (
                  <button
                    type="button"
                    onClick={() =>
                      document.getElementById("tolerance")?.focus()
                    }
                  >
                    Late risk · {Math.round(tolerance)}% <span>Edit</span>
                  </button>
                )}
              </div>
            )}
            {demo && (
              <p className="demo-ask-note">
                Ask is disabled in the demo. Explore the journey form below.
              </p>
            )}
            <div className="workspace">
              <aside className="planner-column">
                <section className="card planner-card">
                  <div className="section-top">
                    <span className="eyebrow">01 / YOUR JOURNEY</span>
                    <Icon name="bus" size={19} />
                  </div>
                  <h2>Where are we going?</h2>
                  <p className="small muted">
                    One route. A little peace of mind.
                  </p>
                  {catalogBusy ? (
                    <div className="planner-loading" role="status">
                      <div className="skeleton" />
                      <div className="skeleton" />
                      <span>Finding supported routes…</span>
                    </div>
                  ) : catalogError ? (
                    <div className="connection-state" role="alert">
                      <Icon name="info" size={28} />
                      <h3>Let’s get connected.</h3>
                      <p>{catalogError}</p>
                      <button
                        type="button"
                        className="primary-button"
                        onClick={() => setRetry((r) => r + 1)}
                      >
                        Retry connection <Icon name="refresh" size={17} />
                      </button>
                      <button
                        type="button"
                        className="text-button"
                        onClick={() => setMode("demo")}
                      >
                        Try labelled demo <Icon name="arrow" size={17} />
                      </button>
                    </div>
                  ) : routes.length === 0 ? (
                    <div className="connection-state">
                      <h3>No routes available yet</h3>
                      <p>The team is still choosing the supported journeys.</p>
                      <button
                        type="button"
                        className="text-button"
                        onClick={() => setRetry((r) => r + 1)}
                      >
                        Refresh routes
                      </button>
                      <button
                        type="button"
                        className="text-button"
                        onClick={() => setMode("demo")}
                      >
                        Try labelled demo
                      </button>
                    </div>
                  ) : (
                    <form id="journey-form" onSubmit={submitJourney}>
                      <label htmlFor="route">Your route</label>
                      <select
                        id="route"
                        value={form.routeId}
                        onChange={(event) =>
                          editForm({ routeId: event.target.value })
                        }
                        required
                      >
                        {routes.map((route) => (
                          <option key={route.route_id} value={route.route_id}>
                            {route.origin.name} → {route.destination.name}
                          </option>
                        ))}
                      </select>
                      {activeRoute && (
                        <div className="route-stops">
                          <div>
                            <span className="stop-dot" />
                            <span>{activeRoute.origin.name}</span>
                          </div>
                          <div className="route-connector">
                            <span />
                            <small>
                              {activeRoute.mode === "bus" ? "Bus" : "Tube"} ·{" "}
                              {activeRoute.line_id === "fixture" || demo
                                ? "demonstration route"
                                : activeRoute.line_id}
                            </small>
                          </div>
                          <div>
                            <span className="stop-dot destination" />
                            <span>{activeRoute.destination.name}</span>
                          </div>
                        </div>
                      )}
                      {latestCoveredHour !== null && (
                        <div className="route-coverage-hint">
                          <p>
                            {activeRoute!.hours_covered.length} recorded hours ·
                            latest{" "}
                            {new Intl.DateTimeFormat("en-GB", {
                              day: "numeric",
                              month: "short",
                              hour: "2-digit",
                              timeZone: zone,
                              timeZoneName: "short",
                            }).format(new Date(latestCoveredHour))}
                          </p>
                          <button
                            type="button"
                            onClick={() =>
                              editForm({
                                deadline: inputDate(
                                  exampleIso ??
                                    new Date(latestCoveredHour).toISOString(),
                                  clock,
                                ),
                              })
                            }
                          >
                            Try a recorded-hour example{" "}
                            <Icon name="arrow" size={13} />
                          </button>
                          <small>
                            This fills a historical deadline. Submit to explore
                            real recorded journeys.
                          </small>
                        </div>
                      )}
                      <label htmlFor="deadline">I need to arrive by</label>
                      <div className="input-with-icon">
                        <Icon name="clock" size={18} />
                        <input
                          id="deadline"
                          type="datetime-local"
                          required
                          value={form.deadline}
                          onChange={(event) =>
                            editForm({ deadline: event.target.value })
                          }
                        />
                      </div>
                      <div className="time-zone">
                        <label htmlFor="timezone">Time zone</label>
                        <select
                          id="timezone"
                          value={clock}
                          onChange={(event) =>
                            changeClock(event.target.value as Clock)
                          }
                        >
                          <option value="local">{browserZone}</option>
                          <option value="utc">UTC (unambiguous)</option>
                        </select>
                      </div>
                      <div className="walk-fields">
                        <div>
                          <label htmlFor="walk-to">Walk to stop</label>
                          <div className="number-input">
                            <input
                              id="walk-to"
                              type="number"
                              min="0"
                              max="60"
                              step="1"
                              required
                              value={
                                Number.isNaN(form.walkTo) ? "" : form.walkTo
                              }
                              onChange={(event) =>
                                editForm({ walkTo: event.target.valueAsNumber })
                              }
                            />
                            <span>min</span>
                          </div>
                        </div>
                        <div>
                          <label htmlFor="walk-from">Walk from stop</label>
                          <div className="number-input">
                            <input
                              id="walk-from"
                              type="number"
                              min="0"
                              max="60"
                              step="1"
                              required
                              value={
                                Number.isNaN(form.walkFrom) ? "" : form.walkFrom
                              }
                              onChange={(event) =>
                                editForm({
                                  walkFrom: event.target.valueAsNumber,
                                })
                              }
                            />
                            <span>min</span>
                          </div>
                        </div>
                      </div>
                      <div className="risk-control">
                        <div className="label-row">
                          <label htmlFor="tolerance">
                            Chance of being late
                          </label>
                          <output htmlFor="tolerance">
                            {Math.round(tolerance)}%
                          </output>
                        </div>
                        <input
                          id="tolerance"
                          type="range"
                          max={Math.max(40, tolerance)}
                          min={Math.min(1, tolerance)}
                          step="1"
                          value={tolerance}
                          onChange={(event) => {
                            setTolerance(Number(event.target.value));
                            setDelay(0);
                          }}
                        />
                        <div className="range-labels">
                          <span>Play it safe</span>
                          <span>A little flexible</span>
                        </div>
                      </div>
                      <label className="checkbox-label">
                        <input
                          type="checkbox"
                          checked={conservative}
                          onChange={(event) => {
                            setConservative(event.target.checked);
                            setDelay(0);
                          }}
                        />
                        <span>
                          Use a conservative estimate
                          <small>
                            Choose using the lower uncertainty bound.
                          </small>
                        </span>
                      </label>
                      <button
                        className="primary-button calculate"
                        type="submit"
                        disabled={curveBusy || askBusy}
                      >
                        {curveBusy
                          ? "Finding your departure…"
                          : dirty
                            ? "Update my journey"
                            : "Find my departure"}
                        <Icon name="arrow" size={18} />
                      </button>
                      <p className="form-footnote">
                        Risk changes update instantly, right here.
                      </p>
                    </form>
                  )}
                </section>
                <div className="planner-note">
                  <Icon name="shield" size={18} />
                  <p>
                    An estimate, not a promise.
                    <br />
                    We’ll always show our uncertainty.
                  </p>
                </div>
              </aside>
              <div className="results-column">
                <section
                  className="card chart-card"
                  aria-busy={curveBusy || catalogBusy}
                >
                  <div className="section-top">
                    <span className="eyebrow">02 / THE BIGGER PICTURE</span>
                    {result && (
                      <span className="computed">
                        <span className="status-dot green" />
                        {demo
                          ? "Local demo"
                          : `Computed in ${result.curve.server_ms.toFixed(1)} ms`}
                      </span>
                    )}
                  </div>
                  <div className="chart-heading">
                    <div>
                      <h2>Your departure window</h2>
                      <p className="small muted">
                        {result ? (
                          <>
                            Arrive by{" "}
                            <strong>
                              {timeLabel(result.request.deadline, clock)}
                            </strong>{" "}
                            ·{" "}
                            {new Intl.DateTimeFormat("en-GB", {
                              day: "numeric",
                              month: "short",
                              timeZone: zone,
                            }).format(new Date(result.request.deadline))}{" "}
                            · {result.route.destination.name} · {zone}
                          </>
                        ) : (
                          "See how your odds change with every minute."
                        )}
                      </p>
                    </div>
                    {result && (
                      <span
                        className={`badge ${fixture || result.curve.data_quality.status === "low_data" ? "badge-amber" : ""}`}
                      >
                        {fixture
                          ? "Synthetic data"
                          : result.curve.data_quality.status === "low_data"
                            ? "Low data"
                            : result.curve.data_quality.status ===
                                "insufficient_data"
                              ? "Insufficient data"
                              : `Up to ${Math.max(0, ...points.map((p) => p.n_trips))} trips per departure time`}
                      </span>
                    )}
                  </div>
                  {lowData && (
                    <div className="low-data-notice" role="status">
                      <Icon name="info" size={20} />
                      <div>
                        <strong>Early estimate · limited observations</strong>
                        <p>
                          Some departure times have fewer than{" "}
                          {MIN_RECOMMENDATION_TRIPS} recorded trips. Estimates
                          there are preliminary, inferred from TfL predictions
                          rather than measured arrivals.
                        </p>
                      </div>
                    </div>
                  )}
                  {curveBusy || catalogBusy ? (
                    <div className="chart-loading" role="status">
                      <div className="skeleton" />
                      <div className="skeleton" />
                      <div className="skeleton" />
                      <span>Putting your journey in perspective…</span>
                    </div>
                  ) : curveError ? (
                    <div className="chart-empty" role="alert">
                      <Icon name="info" size={32} />
                      <h3>We couldn’t load your curve.</h3>
                      <p>{curveError}</p>
                    </div>
                  ) : points.length ? (
                    <DepartureCurve
                      key={result!.request.deadline + result!.request.route_id}
                      points={points}
                      recommended={best}
                      selected={selected}
                      tolerance={tolerance / 100}
                      clock={clock}
                      windowStart={new Date(
                        Date.parse(result!.request.deadline) -
                          result!.request.window_min * 60_000,
                      ).toISOString()}
                      windowEnd={result!.request.deadline}
                    />
                  ) : (
                    <div className="chart-empty">
                      <div className="empty-route-art" aria-hidden="true">
                        <span />
                        <i />
                        <span />
                      </div>
                      <h3>
                        {result
                          ? "A little more data is needed."
                          : "Your next good decision starts here."}
                      </h3>
                      <p>
                        {result
                          ? result.curve.data_quality.basis
                          : "Choose a journey to see when to leave, with your odds of arriving on time."}
                      </p>
                    </div>
                  )}
                  {dirty && (
                    <p className="pending-notice" role="status">
                      Your journey has changed. Update it to see a new departure
                      window.
                    </p>
                  )}
                  {result &&
                    points.length > 0 &&
                    points.length < result.request.window_min + 1 && (
                      <p className="coverage-note">
                        {points.length} of {result.request.window_min + 1}{" "}
                        departure times have usable observations. Blank sections
                        have too little data for an estimate.
                      </p>
                    )}
                  {result && (
                    <div className="data-basis">
                      <Icon name="info" size={15} />
                      <span>{result.curve.data_quality.basis}</span>
                    </div>
                  )}
                </section>
                <div className="below-chart">
                  <section
                    ref={adviceRef}
                    tabIndex={-1}
                    className={`advice-card ${lowData ? "advice-low-data" : ""}`}
                    aria-label="Departure recommendation"
                  >
                    <div className="section-top">
                      <span className="eyebrow">03 / DEPARTURE ADVICE</span>
                      <Icon name="clock" size={20} />
                    </div>
                    {lowData && (
                      <p className="advice-caution">
                        <Icon name="info" size={15} />
                        Limited observations · preliminary curve
                      </p>
                    )}
                    <div aria-live="polite">
                      {best ? (
                        <>
                          <p className="leave-label">
                            {delay
                              ? `If you leave ${delay} minutes later`
                              : "Aim to leave by"}
                          </p>
                          <div className="recommendation">
                            <strong>
                              {selected
                                ? timeLabel(selected.depart_at, clock)
                                : "—"}
                            </strong>
                            <span>
                              {selected
                                ? `${Math.round((conservative ? selected.ci[0] : selected.p_on_time) * 100)}%`
                                : "—"}
                              <small>
                                {conservative
                                  ? "lower-bound chance"
                                  : "chance of being on time"}
                              </small>
                            </span>
                          </div>
                          <p className="advice-note">
                            {delay ? (
                              selected ? (
                                `${Math.round(((conservative ? selected.ci[0] : selected.p_on_time) - (conservative ? best.ci[0] : best.p_on_time)) * 100)} percentage points versus leaving at ${timeLabel(best.depart_at, clock)}.`
                              ) : (
                                "That departure falls outside this curve. Try an earlier journey."
                              )
                            ) : (
                              <>
                                Includes{" "}
                                {result!.request.walk_to_min +
                                  result!.request.walk_from_min}{" "}
                                minutes of walking. A little buffer goes a long
                                way.
                              </>
                            )}
                          </p>
                        </>
                      ) : (
                        <>
                          <h3>
                            {points.length && !hasEligibleDepartures
                              ? "Recommendation pending"
                              : points.length
                                ? "Give yourself more room."
                                : "A time you can feel good about."}
                          </h3>
                          <p className="advice-note">
                            {points.length && !hasEligibleDepartures
                              ? `Explore the curve while data accumulates. Recommendations need at least ${MIN_RECOMMENDATION_TRIPS} recorded trips for a departure time.`
                              : points.length
                                ? "No departure in this window meets your target. Try another deadline, a shorter walk, or a higher tolerance."
                                : "Your recommended departure will appear once a journey has enough data."}
                          </p>
                        </>
                      )}
                    </div>
                    <div className="what-if">
                      <span>What if I leave later?</span>
                      <div className="delay-buttons">
                        {[0, 5, 10, 15].map((minutes) => (
                          <button
                            key={minutes}
                            type="button"
                            disabled={!best}
                            aria-pressed={delay === minutes}
                            onClick={() => setDelay(minutes)}
                            className={delay === minutes ? "selected" : ""}
                          >
                            {minutes === 0 ? "On plan" : `+${minutes} min`}
                          </button>
                        ))}
                      </div>
                    </div>
                  </section>
                  {result ? (
                    <LivePanel
                      key={result.route.route_id}
                      route={result.route}
                      demo={demo || result.route.line_id === "fixture"}
                      offline={isOfflineSnapshot(
                        result.curve.data_quality.basis,
                      )}
                      clock={clock}
                    />
                  ) : (
                    <section className="card live-card">
                      <span className="eyebrow">AT YOUR STOP</span>
                      <h3>Next to arrive</h3>
                      <div className="inline-state">
                        <Icon name="bus" />
                        <p>
                          Live arrivals will appear for your selected route. No
                          journey selected yet.
                        </p>
                      </div>
                    </section>
                  )}
                </div>
              </div>
            </div>
          </>
        )}
        <footer>
          <span className="footer-brand">
            delaylens<span>Made for the moments that matter.</span>
          </span>
          <span>
            Powered by{" "}
            <a
              href="https://tfl.gov.uk/info-for/open-data-users/"
              target="_blank"
              rel="noreferrer"
            >
              TfL Open Data
            </a>
            <span className="footer-divider">/</span>Built at OxHack 2026
          </span>
          <button
            type="button"
            onClick={() => setTab(tab === "plan" ? "method" : "plan")}
          >
            {tab === "plan" ? "How it works" : "Back to planner"}{" "}
            <Icon name="arrow" size={15} />
          </button>
        </footer>
      </main>
    </div>
  );
}
