/**
 * Pure helpers for Ask's voice input (Web Speech API). The browser objects are
 * typed minimally here because TypeScript's DOM library omits SpeechRecognition.
 * In Chrome, recognition audio is sent to Google's speech service.
 */

export interface SpeechAlternativeLike {
  transcript: string;
}
export interface SpeechResultLike {
  readonly isFinal: boolean;
  readonly length: number;
  [index: number]: SpeechAlternativeLike;
}
export interface SpeechResultListLike {
  readonly length: number;
  [index: number]: SpeechResultLike;
}
export interface SpeechRecognitionLike {
  lang: string;
  interimResults: boolean;
  continuous: boolean;
  maxAlternatives: number;
  onresult: ((event: { resultIndex: number; results: SpeechResultListLike }) => void) | null;
  onerror: ((event: { error: string }) => void) | null;
  onend: (() => void) | null;
  start(): void;
  stop(): void;
  abort(): void;
}
export type SpeechRecognitionCtor = new () => SpeechRecognitionLike;

export const SPEECH_LANG = "en-GB";

/** The standard or WebKit-prefixed constructor, or null when unsupported. */
export function speechRecognitionCtor(
  scope: object | undefined,
): SpeechRecognitionCtor | null {
  if (!scope) return null;
  const candidate = scope as {
    SpeechRecognition?: unknown;
    webkitSpeechRecognition?: unknown;
  };
  const ctor = candidate.SpeechRecognition ?? candidate.webkitSpeechRecognition;
  return typeof ctor === "function" ? (ctor as SpeechRecognitionCtor) : null;
}

/** Joined final and interim text across every result received so far. */
export function readTranscript(results: SpeechResultListLike): {
  final: string;
  interim: string;
} {
  let final = "";
  let interim = "";
  for (let i = 0; i < results.length; i++) {
    const result = results[i];
    const text = result.length ? result[0].transcript : "";
    if (result.isFinal) final += text;
    else interim += text;
  }
  return { final: tidy(final), interim: tidy(interim) };
}

const tidy = (text: string) => text.replace(/\s+/g, " ").trim();

/** Text to show in the input while listening: final words then interim ones. */
export function liveText(transcript: { final: string; interim: string }): string {
  return tidy(`${transcript.final} ${transcript.interim}`);
}

/**
 * Whether a finished recognition session should send its transcript to Ask.
 * A session we aborted (Ask became busy, or the button unmounted) or one that
 * reported an error never submits, even if the browser still fires `end` with text.
 */
export function shouldSubmitOnEnd(session: {
  final: string;
  failed: boolean;
  cancelled: boolean;
}): boolean {
  return Boolean(session.final.trim()) && !session.failed && !session.cancelled;
}

/** User-facing message for a SpeechRecognition error code, or "" to stay quiet. */
export function speechErrorMessage(code: string): string {
  switch (code) {
    case "aborted":
      return "";
    case "not-allowed":
    case "service-not-allowed":
      return "Microphone access was blocked. Allow the microphone for this site in your browser settings, or type your question.";
    case "no-speech":
      return "We didn’t hear anything. Press the microphone and try again, or type your question.";
    case "audio-capture":
      return "No microphone was found. Check that one is connected, or type your question.";
    case "network":
      return "Speech recognition needs a network connection to the browser’s speech service. Type your question instead.";
    case "language-not-supported":
      return "British English speech recognition is not available in this browser. Type your question instead.";
    default:
      return "Voice input stopped unexpectedly. Try again or type your question.";
  }
}

export const VOICE_UNSUPPORTED =
  "Voice input isn’t supported in this browser. Try Chrome or Edge, or type your question.";
export const VOICE_PRIVACY =
  "In Chrome, speech recognition sends your audio to Google’s speech service.";
