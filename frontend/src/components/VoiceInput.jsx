import { useEffect, useRef, useState } from "react";
import SpeechRecognition, {
  useSpeechRecognition,
} from "react-speech-recognition";
import { Mic, MicOff } from "lucide-react";

function VoiceInput({ setQuestion }) {
  const { transcript, resetTranscript, listening, browserSupportsSpeechRecognition } = useSpeechRecognition();
  const [isActive, setIsActive] = useState(false);
  const transcriptRef = useRef("");

  // Keep ref in sync
  useEffect(() => {
    transcriptRef.current = transcript;
  }, [transcript]);

  if (!browserSupportsSpeechRecognition) {
    return null; // Silently hide if not supported
  }

  const toggleListening = () => {
    if (listening) {
      // Stop listening
      SpeechRecognition.stopListening();
      setIsActive(false);
      // Small delay to finalize transcription
      setTimeout(() => {
        const heard = transcriptRef.current.trim();
        if (heard) {
          setQuestion(heard);
        }
        resetTranscript();
      }, 300);
    } else {
      // Start listening
      resetTranscript();
      transcriptRef.current = "";
      setIsActive(true);
      SpeechRecognition.startListening({ continuous: true, language: "en-US" });
    }
  };

  return (
    <button
      onClick={toggleListening}
      title={listening ? "Stop recording" : "Start voice input"}
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        width: 38,
        height: 38,
        borderRadius: 8,
        border: listening ? "2px solid #ef4444" : "2px solid #e2e8f0",
        background: listening ? "#fef2f2" : "#fff",
        color: listening ? "#ef4444" : "#64748b",
        cursor: "pointer",
        transition: "all 0.2s",
        flexShrink: 0,
        padding: 0,
      }}
      onMouseEnter={(e) => {
        if (!listening) {
          e.currentTarget.style.borderColor = "#0ea5e9";
          e.currentTarget.style.color = "#0ea5e9";
          e.currentTarget.style.background = "#f0f9ff";
        }
      }}
      onMouseLeave={(e) => {
        if (!listening) {
          e.currentTarget.style.borderColor = "#e2e8f0";
          e.currentTarget.style.color = "#64748b";
          e.currentTarget.style.background = "#fff";
        }
      }}
    >
      {listening ? <MicOff size={18} /> : <Mic size={18} />}
    </button>
  );
}

export default VoiceInput;
