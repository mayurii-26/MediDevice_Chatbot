import { useEffect, useRef } from "react";
import SpeechRecognition, {
  useSpeechRecognition,
} from "react-speech-recognition";

function VoiceInput({ setQuestion }) {
  const { transcript, resetTranscript, listening } = useSpeechRecognition();
  const transcriptRef = useRef("");

  // Keep a ref always in sync with the latest transcript
  // so stopListening can read the real-time value, not a stale closure
  useEffect(() => {
    transcriptRef.current = transcript;
  }, [transcript]);

  if (!SpeechRecognition.browserSupportsSpeechRecognition()) {
    return (
      <p style={{ color: "#6b7280", fontSize: "0.88rem" }}>
        ⚠️ Voice input is not supported in this browser. Please use Chrome.
      </p>
    );
  }

  const startListening = () => {
    resetTranscript();
    transcriptRef.current = "";
    SpeechRecognition.startListening({ continuous: true, language: "en-US" });
  };

  const stopListening = () => {
    SpeechRecognition.stopListening();
    // Small delay so browser finalises the last word before we read it
    setTimeout(() => {
      const heard = transcriptRef.current.trim();
      if (heard) {
        setQuestion(heard);
      }
    }, 300);
  };

  return (
    <div>
      <button
        className="voice-btn"
        onClick={startListening}
        disabled={listening}
      >
        🎤 {listening ? "Listening..." : "Start Voice"}
      </button>

      <button
        className="voice-btn stop"
        onClick={stopListening}
        disabled={!listening}
      >
        ⏹ Stop & Use
      </button>

      {listening && (
        <p style={{ marginTop: "8px", fontSize: "0.88rem", color: "#dc2626", fontWeight: 600 }}>
          🔴 Speak now...
        </p>
      )}

      {transcript && (
        <p style={{ marginTop: "6px", fontSize: "0.88rem", color: "#374151" }}>
          Heard: <em>{transcript}</em>
        </p>
      )}
    </div>
  );
}

export default VoiceInput;
