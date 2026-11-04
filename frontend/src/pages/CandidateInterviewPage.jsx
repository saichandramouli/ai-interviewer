import React, { useState, useEffect, useRef } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';

export default function CandidateInterviewPage() {
  const [searchParams] = useSearchParams();
  const token = searchParams.get('token');
  const navigate = useNavigate();

  // Session & interview state
  const [session, setSession] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [step, setStep] = useState('loading'); // 'disclosure', 'consent', 'interview', 'completed'

  // Consent state
  const [consentChecked, setConsentChecked] = useState(false);
  const [submittingConsent, setSubmittingConsent] = useState(false);

  // Audio recording state
  const [micPermission, setMicPermission] = useState('prompt'); // 'prompt', 'granted', 'denied'
  const [isRecording, setIsRecording] = useState(false);
  const [recordingSeconds, setRecordingSeconds] = useState(0);
  const [audioBlob, setAudioBlob] = useState(null);
  const [isProcessing, setIsProcessing] = useState(false);
  const [latestCandidateTranscript, setLatestCandidateTranscript] = useState('');
  const [currentMessage, setCurrentMessage] = useState('');
  const [isPlayingAudio, setIsPlayingAudio] = useState(false);

  // Media references
  const mediaRecorderRef = useRef(null);
  const audioChunksRef = useRef([]);
  const timerIntervalRef = useRef(null);
  const currentAudioElementRef = useRef(null);

  // 1. Fetch Candidate Session Info
  useEffect(() => {
    // If token is in URL query parameter, store in sessionStorage and strip from URL
    let activeToken = token;
    if (token) {
      sessionStorage.setItem('candidate_interview_token', token);
      // Clean query parameter from browser address bar without reload
      const cleanUrl = window.location.pathname;
      window.history.replaceState({}, document.title, cleanUrl);
    } else {
      activeToken = sessionStorage.getItem('candidate_interview_token');
    }

    if (!activeToken) {
      setError('Missing interview access token. Please check the invitation link provided to you.');
      setLoading(false);
      return;
    }

    async function loadSession() {
      try {
        const resp = await fetch(`/api/v1/candidate/session/`, {
          headers: {
            Authorization: `Bearer ${activeToken}`,
          },
        });
        const data = await resp.json();

        if (!resp.ok) {
          setError(data.detail || 'Unable to access interview session.');
          setLoading(false);
          return;
        }

        setSession(data);
        if (data.status === 'completed') {
          setStep('completed');
        } else if (data.candidate.consent_status === 'granted') {
          setStep('interview');
          // If already in progress, set latest message
          const lastAi = data.transcripts.filter((t) => t.speaker === 'ai').slice(-1)[0];
          if (lastAi) {
            setCurrentMessage(lastAi.text);
          }
        } else {
          setStep('disclosure');
        }
      } catch (err) {
        setError('Network error contacting interview server. Please check your internet connection.');
      } finally {
        setLoading(false);
      }
    }

    loadSession();
  }, [token]);

  // Clean up audio tracks on unmount
  useEffect(() => {
    return () => {
      if (timerIntervalRef.current) clearInterval(timerIntervalRef.current);
      if (mediaRecorderRef.current && mediaRecorderRef.current.stream) {
        mediaRecorderRef.current.stream.getTracks().forEach((track) => track.stop());
      }
      if (currentAudioElementRef.current) {
        currentAudioElementRef.current.pause();
      }
    };
  }, []);

  const getActiveToken = () => {
    return sessionStorage.getItem('candidate_interview_token') || token || '';
  };

  // 2. Handle Consent Submission
  const handleGrantConsent = async () => {
    if (!consentChecked) return;
    setSubmittingConsent(true);
    setError(null);
    const activeToken = getActiveToken();

    try {
      const resp = await fetch('/api/v1/candidate/consent/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${activeToken}`,
        },
        body: JSON.stringify({
          consent_granted: true,
          consent_method: 'Candidate Web Portal Form',
        }),
      });

      const data = await resp.json();
      if (!resp.ok) {
        setError(data.detail || 'Failed to record consent.');
        setSubmittingConsent(false);
        return;
      }

      // Request microphone permission immediately after consent
      await requestMicrophonePermission();
      // Start the interview
      await handleStartInterview();
    } catch (err) {
      setError('Failed to record consent. Please try again.');
      setSubmittingConsent(false);
    }
  };

  // 3. Request Microphone Access
  const requestMicrophonePermission = async () => {
    try {
      if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        setMicPermission('denied');
        setError('Your browser does not support microphone recording. Please use modern Chrome, Edge, or Firefox.');
        return false;
      }

      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      // Keep track of stream for later recording and release
      stream.getTracks().forEach((track) => track.stop()); // release test stream
      setMicPermission('granted');
      return true;
    } catch (err) {
      setMicPermission('denied');
      setError('Microphone permission denied. Please allow microphone access in your browser settings to continue the interview.');
      return false;
    }
  };

  // 4. Start Interview & Fetch First Utterance
  const handleStartInterview = async () => {
    const activeToken = getActiveToken();
    try {
      const resp = await fetch('/api/v1/candidate/start/', {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${activeToken}`,
        },
      });
      const data = await resp.json();
      if (!resp.ok) {
        setError(data.detail || 'Could not initiate interview session.');
        return;
      }

      setStep('interview');
      setCurrentMessage(data.current_message);
      // Play initial greeting
      await playInterviewerSpeech(data.current_message);
    } catch (err) {
      setError('Network error starting interview.');
    }
  };

  // 5. Synthesize & Play AI Speech
  const playInterviewerSpeech = async (messageText) => {
    if (!messageText) return;
    setIsPlayingAudio(true);
    const activeToken = getActiveToken();

    try {
      const resp = await fetch('/api/v1/candidate/synthesize-speech/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${activeToken}`,
        },
        body: JSON.stringify({ message: messageText }),
      });

      if (!resp.ok) {
        console.warn('Speech synthesis unavailable, falling back to visual text.');
        setIsPlayingAudio(false);
        return;
      }

      const audioBlob = await resp.blob();
      const audioUrl = URL.createObjectURL(audioBlob);
      const audio = new Audio(audioUrl);
      currentAudioElementRef.current = audio;

      audio.onended = () => {
        setIsPlayingAudio(false);
        URL.revokeObjectURL(audioUrl);
      };

      audio.onerror = () => {
        setIsPlayingAudio(false);
        URL.revokeObjectURL(audioUrl);
      };

      await audio.play();
    } catch (err) {
      console.warn('Audio playback error:', err);
      setIsPlayingAudio(false);
    }
  };

  // 6. Audio Recording Controls
  const startRecording = async () => {
    setError(null);
    setAudioBlob(null);
    audioChunksRef.current = [];

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      // Pick best supported MIME format
      let mimeType = 'audio/webm';
      if (MediaRecorder.isTypeSupported('audio/webm;codecs=opus')) {
        mimeType = 'audio/webm;codecs=opus';
      } else if (MediaRecorder.isTypeSupported('audio/ogg;codecs=opus')) {
        mimeType = 'audio/ogg;codecs=opus';
      } else if (MediaRecorder.isTypeSupported('audio/wav')) {
        mimeType = 'audio/wav';
      }

      const mediaRecorder = new MediaRecorder(stream, { mimeType });
      mediaRecorderRef.current = mediaRecorder;

      mediaRecorder.ondataavailable = (event) => {
        if (event.data && event.data.size > 0) {
          audioChunksRef.current.push(event.data);
        }
      };

      mediaRecorder.onstop = () => {
        const blob = new Blob(audioChunksRef.current, { type: mimeType });
        setAudioBlob(blob);
        // Release tracks
        stream.getTracks().forEach((track) => track.stop());
      };

      mediaRecorder.start(250); // Slice every 250ms
      setIsRecording(true);
      setRecordingSeconds(0);

      timerIntervalRef.current = setInterval(() => {
        setRecordingSeconds((prev) => prev + 1);
      }, 1000);
    } catch (err) {
      setError('Could not access microphone. Ensure permissions are granted.');
    }
  };

  const stopRecording = () => {
    if (mediaRecorderRef.current && isRecording) {
      mediaRecorderRef.current.stop();
      setIsRecording(false);
      if (timerIntervalRef.current) {
        clearInterval(timerIntervalRef.current);
      }
    }
  };

  // 7. Submit Spoken Turn to Backend
  const submitTurn = async () => {
    if (!audioBlob) {
      setError('No recorded audio available to submit.');
      return;
    }

    setIsProcessing(true);
    setError(null);

    const formData = new FormData();
    formData.append('audio', audioBlob, 'candidate-turn.webm');

    const activeToken = getActiveToken();
    try {
      const resp = await fetch('/api/v1/candidate/submit-turn/', {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${activeToken}`,
        },
        body: formData,
      });

      const data = await resp.json();
      if (!resp.ok) {
        setError(data.detail || 'Failed to process candidate response.');
        setIsProcessing(false);
        return;
      }

      setLatestCandidateTranscript(data.candidate_transcript || '');
      setCurrentMessage(data.interviewer_message || '');
      setAudioBlob(null);

      if (data.is_completed) {
        setStep('completed');
      } else if (data.interviewer_message) {
        // Synthesize next question or follow-up
        await playInterviewerSpeech(data.interviewer_message);
      }
    } catch (err) {
      setError('Network error submitting response. You can safely retry.');
    } finally {
      setIsProcessing(false);
    }
  };

  // Render Loading
  if (loading) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100vh', background: '#0f172a', color: '#94a3b8' }}>
        Loading secure interview portal...
      </div>
    );
  }

  // Render Error if invalid token or fatal
  if (error && !session) {
    return (
      <div style={{ minHeight: '100vh', background: '#0f172a', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '1.5rem' }}>
        <div style={{ background: '#1e293b', padding: '2rem', borderRadius: '0.75rem', maxWidth: '480px', width: '100%', border: '1px solid #334155', color: '#f8fafc' }}>
          <h2 style={{ color: '#ef4444', marginBottom: '1rem' }}>Interview Access Error</h2>
          <p style={{ color: '#94a3b8', lineHeight: 1.6 }}>{error}</p>
        </div>
      </div>
    );
  }

  return (
    <div style={{ minHeight: '100vh', background: '#0f172a', color: '#f8fafc', display: 'flex', flexDirection: 'column' }}>
      {/* Header */}
      <header style={{ padding: '1.25rem 2rem', background: '#1e293b', borderBottom: '1px solid #334155', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <h1 style={{ fontSize: '1.25rem', fontWeight: 600, margin: 0 }}>AI Interviewer</h1>
          <p style={{ fontSize: '0.875rem', color: '#94a3b8', margin: '0.25rem 0 0' }}>{session?.job?.title || 'Technical Assessment'}</p>
        </div>
        <div style={{ textAlign: 'right' }}>
          <span style={{ fontSize: '0.875rem', color: '#cbd5e1' }}>Candidate: <strong>{session?.candidate?.name}</strong></span>
        </div>
      </header>

      {/* Main Body */}
      <main style={{ flex: 1, padding: '2rem', display: 'flex', justifyContent: 'center', alignItems: 'center' }}>
        {step === 'disclosure' && (
          <div style={{ background: '#1e293b', border: '1px solid #334155', borderRadius: '0.75rem', padding: '2rem', maxWidth: '640px', width: '100%' }}>
            <h2 style={{ fontSize: '1.5rem', fontWeight: 600, marginBottom: '1rem', color: '#38bdf8' }}>
              Interview Overview & Consent Disclosure
            </h2>
            <div style={{ color: '#cbd5e1', lineHeight: 1.6, fontSize: '0.925rem' }}>
              <p>Welcome, <strong>{session.candidate.name}</strong>. You are about to participate in an AI-assisted technical interview for the position of <strong>{session.job.title}</strong>.</p>
              
              <h3 style={{ fontSize: '1.05rem', color: '#f8fafc', marginTop: '1.25rem' }}>Important Information</h3>
              <ul style={{ paddingLeft: '1.25rem', margin: '0.5rem 0 1.25rem' }}>
                <li>This interview uses speech recognition (Deepgram) and AI dialogue synthesis (NVIDIA Nemotron).</li>
                <li>Your spoken answers will be transcribed into text and evaluated against job-related competencies.</li>
                <li><strong>Privacy Assurance:</strong> Audio recordings are used only for real-time transcription and are immediately discarded. No permanent audio files are stored.</li>
                <li>Maximum interview duration: <strong>{session.disclosure.duration_limit_minutes} minutes</strong>.</li>
              </ul>

              <div style={{ background: '#0f172a', padding: '1rem', borderRadius: '0.5rem', border: '1px solid #334155', marginTop: '1.5rem', display: 'flex', alignItems: 'flex-start', gap: '0.75rem' }}>
                <input
                  type="checkbox"
                  id="consentCheckbox"
                  checked={consentChecked}
                  onChange={(e) => setConsentChecked(e.target.checked)}
                  style={{ marginTop: '0.25rem', width: '1.1rem', height: '1.1rem', cursor: 'pointer' }}
                />
                <label htmlFor="consentCheckbox" style={{ fontSize: '0.875rem', cursor: 'pointer' }}>
                  I understand that this interview is conducted by an AI interviewer. I grant consent for my audio responses to be processed and transcribed for employment assessment purposes.
                </label>
              </div>

              {error && <p style={{ color: '#ef4444', marginTop: '1rem', fontSize: '0.875rem' }}>{error}</p>}

              <button
                onClick={handleGrantConsent}
                disabled={!consentChecked || submittingConsent}
                style={{
                  width: '100%',
                  marginTop: '1.5rem',
                  padding: '0.75rem',
                  background: consentChecked ? '#0284c7' : '#334155',
                  color: '#ffffff',
                  border: 'none',
                  borderRadius: '0.5rem',
                  fontSize: '1rem',
                  fontWeight: 600,
                  cursor: consentChecked && !submittingConsent ? 'pointer' : 'not-allowed',
                }}
              >
                {submittingConsent ? 'Recording Consent & Connecting...' : 'Grant Consent & Enter Interview'}
              </button>
            </div>
          </div>
        )}

        {step === 'interview' && (
          <div style={{ background: '#1e293b', border: '1px solid #334155', borderRadius: '0.75rem', padding: '2rem', maxWidth: '720px', width: '100%', display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
            {/* Status bar */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid #334155', paddingBottom: '0.75rem' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <span style={{ width: '10px', height: '10px', borderRadius: '50%', background: isRecording ? '#ef4444' : '#10b981' }} />
                <span style={{ fontSize: '0.875rem', color: '#94a3b8' }}>
                  {isRecording ? 'Listening (Microphone Active)' : isPlayingAudio ? 'Interviewer Speaking' : 'Awaiting Your Response'}
                </span>
              </div>
              <span style={{ fontSize: '0.875rem', color: '#94a3b8' }}>Interview In Progress</span>
            </div>

            {/* AI Utterance Area */}
            <div style={{ background: '#0f172a', padding: '1.5rem', borderRadius: '0.5rem', border: '1px solid #334155' }}>
              <h3 style={{ fontSize: '0.875rem', textTransform: 'uppercase', color: '#38bdf8', letterSpacing: '0.05em', margin: '0 0 0.5rem' }}>
                AI Interviewer
              </h3>
              <p style={{ fontSize: '1.15rem', lineHeight: 1.6, margin: 0, color: '#f8fafc' }}>
                {currentMessage || 'Loading question...'}
              </p>
              {isPlayingAudio && (
                <div style={{ marginTop: '0.75rem', fontSize: '0.8rem', color: '#38bdf8', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                  <span>🔊 Spoken audio playing...</span>
                </div>
              )}
            </div>

            {/* Candidate Transcript Preview */}
            {latestCandidateTranscript && (
              <div style={{ background: '#1e293b', padding: '1rem', borderRadius: '0.5rem', border: '1px solid #475569' }}>
                <h4 style={{ fontSize: '0.8rem', textTransform: 'uppercase', color: '#94a3b8', margin: '0 0 0.25rem' }}>
                  Your Transcribed Response
                </h4>
                <p style={{ margin: 0, fontSize: '0.95rem', color: '#cbd5e1', fontStyle: 'italic' }}>
                  "{latestCandidateTranscript}"
                </p>
              </div>
            )}

            {/* Error Banner */}
            {error && (
              <div style={{ background: '#450a0a', border: '1px solid #b91c1c', padding: '0.75rem 1rem', borderRadius: '0.5rem', color: '#fca5a5', fontSize: '0.875rem' }}>
                {error}
              </div>
            )}

            {/* Recording Controls */}
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '1rem', marginTop: '0.5rem' }}>
              {isRecording ? (
                <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '0.75rem' }}>
                  <div style={{ color: '#ef4444', fontWeight: 600, fontSize: '1.1rem' }}>
                    Recording: {recordingSeconds}s
                  </div>
                  <button
                    onClick={stopRecording}
                    style={{
                      padding: '0.75rem 2rem',
                      background: '#ef4444',
                      color: '#ffffff',
                      border: 'none',
                      borderRadius: '2rem',
                      fontWeight: 600,
                      cursor: 'pointer',
                      fontSize: '1rem',
                      boxShadow: '0 0 15px rgba(239, 68, 68, 0.4)',
                    }}
                  >
                    ⏹ Stop Recording
                  </button>
                </div>
              ) : (
                <div style={{ display: 'flex', gap: '1rem' }}>
                  {!audioBlob ? (
                    <button
                      onClick={startRecording}
                      disabled={isProcessing || isPlayingAudio}
                      style={{
                        padding: '0.75rem 2rem',
                        background: isProcessing || isPlayingAudio ? '#334155' : '#0284c7',
                        color: '#ffffff',
                        border: 'none',
                        borderRadius: '2rem',
                        fontWeight: 600,
                        cursor: isProcessing || isPlayingAudio ? 'not-allowed' : 'pointer',
                        fontSize: '1rem',
                      }}
                    >
                      🎙 Start Speaking
                    </button>
                  ) : (
                    <div style={{ display: 'flex', gap: '0.75rem' }}>
                      <button
                        onClick={startRecording}
                        disabled={isProcessing}
                        style={{
                          padding: '0.75rem 1.25rem',
                          background: '#334155',
                          color: '#f8fafc',
                          border: 'none',
                          borderRadius: '0.5rem',
                          cursor: 'pointer',
                        }}
                      >
                        Re-record
                      </button>
                      <button
                        onClick={submitTurn}
                        disabled={isProcessing}
                        style={{
                          padding: '0.75rem 2rem',
                          background: '#10b981',
                          color: '#ffffff',
                          border: 'none',
                          borderRadius: '0.5rem',
                          fontWeight: 600,
                          cursor: isProcessing ? 'not-allowed' : 'pointer',
                        }}
                      >
                        {isProcessing ? 'Processing Response...' : 'Submit Spoken Answer →'}
                      </button>
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        )}

        {step === 'completed' && (
          <div style={{ background: '#1e293b', border: '1px solid #334155', borderRadius: '0.75rem', padding: '2.5rem', maxWidth: '580px', width: '100%', textAlign: 'center' }}>
            <div style={{ fontSize: '3rem', marginBottom: '1rem' }}>🎉</div>
            <h2 style={{ fontSize: '1.5rem', fontWeight: 600, marginBottom: '0.75rem', color: '#10b981' }}>
              Interview Completed
            </h2>
            <p style={{ color: '#cbd5e1', lineHeight: 1.6, marginBottom: '1.5rem' }}>
              Thank you, <strong>{session?.candidate?.name}</strong>. Your interview for <strong>{session?.job?.title}</strong> has concluded. Your responses have been securely delivered to the recruiting team for review.
            </p>
            <p style={{ color: '#94a3b8', fontSize: '0.875rem' }}>
              You may now safely close this browser window.
            </p>
          </div>
        )}
      </main>
    </div>
  );
}

