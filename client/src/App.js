import React, { useState } from "react";
import LivekitVoiceRoom from "./LivekitVoiceRoom";

function App() {
  const [token, setToken] = useState(null);
  //const room = "client-demo-room"; // fixed value, no need for useState

  const joinRoom = async () => {
    const identity = "client-user-" + Math.floor(Math.random() * 1000);
    const response = await fetch(
      `http://localhost:8000/get-livekit-token?identity=${identity}&room=client-demo-room`
    );
    const data = await response.json();
    setToken(data.token);
  };

  return (
    <div style={{ padding: "2rem" }}>
      <h1>🎙️ AI Agent Voice Demo</h1>
      {!token ? (
        <>
          <button onClick={joinRoom}>Join Call with AI Agent</button>
        </>
      ) : (
        <LivekitVoiceRoom token={token} url="wss://friday-1-few4r3qf.livekit.cloud" />
      )}
    </div>
  );
}

export default App;
