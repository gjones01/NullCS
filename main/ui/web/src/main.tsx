import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import "./index.css";

type ErrorBoundaryState = { error: Error | null };

class RootErrorBoundary extends React.Component<React.PropsWithChildren, ErrorBoundaryState> {
  state: ErrorBoundaryState = { error: null };

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { error };
  }

  componentDidCatch(error: Error, info: React.ErrorInfo) {
    console.error("NullCS UI render failure", error, info);
  }

  render() {
    if (this.state.error) {
      return (
        <div style={{ minHeight: "100vh", display: "grid", placeItems: "center", background: "#06070c", color: "#f5f7ff", padding: "24px" }}>
          <div style={{ width: "min(720px, 100%)", border: "1px solid rgba(195,208,255,0.18)", borderRadius: "24px", background: "rgba(11,16,29,0.82)", padding: "24px", boxShadow: "0 20px 60px rgba(0,0,0,0.35)" }}>
            <div style={{ fontSize: "12px", letterSpacing: "0.18em", textTransform: "uppercase", color: "#99a3bf", marginBottom: "10px" }}>UI runtime error</div>
            <h1 style={{ margin: "0 0 12px", fontSize: "32px" }}>The page hit a render fault.</h1>
            <p style={{ margin: "0 0 16px", color: "#99a3bf", lineHeight: 1.6 }}>The UI stayed alive and caught the exception instead of dropping to a blank screen. Reload after the fix or inspect the message below.</p>
            <pre style={{ margin: 0, whiteSpace: "pre-wrap", overflowWrap: "anywhere", color: "#f5b4c2" }}>{this.state.error.message}</pre>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <RootErrorBoundary>
      <App />
    </RootErrorBoundary>
  </React.StrictMode>
);
