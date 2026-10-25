import { test } from "node:test";
import assert from "node:assert/strict";
import {
  liveText,
  readTranscript,
  shouldSubmitOnEnd,
  speechErrorMessage,
  speechRecognitionCtor,
  type SpeechResultLike,
} from "../src/speech.ts";

const result = (transcript: string, isFinal: boolean): SpeechResultLike => ({
  isFinal,
  length: 1,
  0: { transcript },
});

test("feature detection prefers the standard constructor, then WebKit, else null", () => {
  class Standard {}
  class Webkit {}
  assert.equal(speechRecognitionCtor({ SpeechRecognition: Standard }), Standard);
  assert.equal(speechRecognitionCtor({ webkitSpeechRecognition: Webkit }), Webkit);
  assert.equal(speechRecognitionCtor({}), null);
  assert.equal(speechRecognitionCtor({ SpeechRecognition: "nope" }), null);
  assert.equal(speechRecognitionCtor(undefined), null);
});

test("transcript separates final and interim words", () => {
  const list = {
    length: 2,
    0: result("I need to be at Tottenham Court Road ", true),
    1: result(" by 5pm", false),
  };
  const transcript = readTranscript(list);
  assert.deepEqual(transcript, {
    final: "I need to be at Tottenham Court Road",
    interim: "by 5pm",
  });
  assert.equal(liveText(transcript), "I need to be at Tottenham Court Road by 5pm");
});

test("empty results and empty alternatives are ignored", () => {
  assert.deepEqual(readTranscript({ length: 0 }), { final: "", interim: "" });
  const empty: SpeechResultLike = { isFinal: true, length: 0 };
  assert.deepEqual(readTranscript({ length: 1, 0: empty }), { final: "", interim: "" });
  assert.equal(liveText({ final: "", interim: "" }), "");
});

test("error codes map to helpful messages; aborted stays quiet", () => {
  assert.equal(speechErrorMessage("aborted"), "");
  assert.match(speechErrorMessage("not-allowed"), /Microphone access was blocked/);
  assert.match(speechErrorMessage("service-not-allowed"), /blocked/);
  assert.match(speechErrorMessage("no-speech"), /didn’t hear/);
  assert.match(speechErrorMessage("audio-capture"), /No microphone/);
  assert.match(speechErrorMessage("network"), /network/);
  assert.match(speechErrorMessage("something-new"), /stopped unexpectedly/);
});

test("an aborted voice session never submits, even if end fires with a transcript", () => {
  // Regression: pressing the text Ask button while listening made Ask busy, which
  // aborted recognition; Chrome then fired `end` with text and a second POST went out.
  assert.equal(
    shouldSubmitOnEnd({ final: "when should I leave", failed: false, cancelled: true }),
    false,
  );
});

test("a voice session submits only a non-empty final transcript without errors", () => {
  assert.equal(shouldSubmitOnEnd({ final: "when should I leave", failed: false, cancelled: false }), true);
  assert.equal(shouldSubmitOnEnd({ final: "   ", failed: false, cancelled: false }), false);
  assert.equal(shouldSubmitOnEnd({ final: "when should I leave", failed: true, cancelled: false }), false);
});
