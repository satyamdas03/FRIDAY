// client/src/LivekitVoiceRoom.js
import React, { useEffect, useRef } from "react";
import {
    Room,
    RoomEvent,
    createLocalAudioTrack,
} from "livekit-client";

const LivekitVoiceRoom = ({ token, url }) => {
    const roomRef = useRef(new Room());
    const audioEl = useRef(null);

    useEffect(() => {
        const currentRoom = roomRef.current;

        const connectToRoom = async () => {
            try {
                const audioTrack = await createLocalAudioTrack();

                await currentRoom.connect(url, token, {
                    audio: true,
                    video: false,
                });

                currentRoom.localParticipant.publishTrack(audioTrack);

                currentRoom.on(RoomEvent.TrackSubscribed, (track, publication, participant) => {
                    if (track.kind === "audio") {
                        track.attach(audioEl.current);
                    }
                });
            } catch (error) {
                console.error("Failed to connect to LiveKit room:", error);
            }
        };

        connectToRoom();

        return () => {
            currentRoom.disconnect();
        };
    }, [token, url]);

    return (
        <div>
            <h2>🔊 Talking to Supriya (AI Agent)...</h2>
            <audio ref={audioEl} autoPlay />
        </div>
    );
};

export default LivekitVoiceRoom;
