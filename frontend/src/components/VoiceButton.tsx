import { useEffect, useRef, useState } from "react";
import Icon from "./Icon";
import {
  SPEECH_LANG,
  VOICE_PRIVACY,
  VOICE_UNSUPPORTED,
  liveText,
  readTranscript,
  speechErrorMessage,
  speechRecognitionCtor,
  type SpeechRecognitionLike,
} from "../speech";

export type VoiceTone = "info" | "error";

interface Props {
  disabled: boolean;
  /** Interim words while listening, shown in the Ask input. */
  onInterim: (text: string) => void;
  /** The final transcript; the caller submits it to /api/ask. */
  onFinal: (text: string) => void;
  onStatus: (message: string, tone: VoiceTone) => void;
}

/** Microphone for Ask DelayLens using the browser's Web Speech API (en-GB). */
export default function VoiceButton({
  disabled,
  onInterim,
  onFinal,
  onStatus,
}: Props) {
  const [Ctor] = useState(() =>
    speechRecognitionCtor(typeof window === "undefined" ? undefined : window),
  );
  const [listening, setListening] = useState(false);
  const recognition = useRef<SpeechRecognitionLike | null>(null);
  const callbacks = useRef({ onInterim, onFinal, onStatus });
  callbacks.current = { onInterim, onFinal, onStatus };

  useEffect(() => () => recognition.current?.abort(), []);
  useEffect(() => {
    if (disabled) recognition.current?.abort();
  }, [disabled]);

  function start() {
    if (!Ctor) {
      callbacks.current.onStatus(VOICE_UNSUPPORTED, "info");
      return;
    }
    if (disabled) return;
    const rec = new Ctor();
    rec.lang = SPEECH_LANG;
    rec.interimResults = true;
    rec.continuous = false;
    rec.maxAlternatives = 1;
    let final = "";
    let failed = false;
    rec.onresult = (event) => {
      const transcript = readTranscript(event.results);
      final = transcript.final;
      callbacks.current.onInterim(liveText(transcript));
    };
    rec.onerror = (event) => {
      failed = true;
      const message = speechErrorMessage(event.error);
      // "aborted" is quiet: clear the listening prompt instead of leaving it up.
      callbacks.current.onStatus(message, message ? "error" : "info");
    };
    rec.onend = () => {
      recognition.current = null;
      setListening(false);
      if (final) {
        callbacks.current.onStatus(
          `Heard “${final}”. Asking DelayLens…`,
          "info",
        );
        callbacks.current.onFinal(final);
      } else if (!failed) {
        callbacks.current.onStatus(speechErrorMessage("no-speech"), "error");
      }
    };
    recognition.current = rec;
    try {
      rec.start();
      setListening(true);
      callbacks.current.onStatus(
        `Listening… ask your question, then pause. ${VOICE_PRIVACY}`,
        "info",
      );
    } catch {
      recognition.current = null;
      callbacks.current.onStatus(speechErrorMessage("unknown"), "error");
    }
  }

  function stop() {
    recognition.current?.stop();
  }

  if (!Ctor)
    return (
      <button
        type="button"
        className="mic-button"
        aria-disabled="true"
        aria-label="Voice input (not supported in this browser)"
        title={VOICE_UNSUPPORTED}
        onClick={start}
      >
        <Icon name="mic" size={18} />
      </button>
    );

  return (
    <button
      type="button"
      className={listening ? "mic-button listening" : "mic-button"}
      aria-pressed={listening}
      aria-label={listening ? "Stop listening" : "Ask by voice"}
      title={
        listening
          ? "Stop listening"
          : `Ask by voice (British English). ${VOICE_PRIVACY}`
      }
      disabled={disabled && !listening}
      onClick={listening ? stop : start}
    >
      <Icon name={listening ? "stop" : "mic"} size={18} />
    </button>
  );
}
