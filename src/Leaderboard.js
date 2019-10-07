import React, { useState, useEffect } from "react";
import Modal from "react-bootstrap/Modal";
import "./Leaderboard.css";
import $ from "jquery";
import LeaderboardEntry from "./LeaderboardEntry.js";

export default function Leaderboard(props) {
    const [leaderboard, setLeaderboard] = useState([]);
    useEffect(() => {
        if (props.show) {
            if (props.memes) {
                $.post("/memeboard", (data) => {
                    setLeaderboard(data);
                });
            } else {
                $.post("/leaderboard", (data) => {
                    setLeaderboard(data);
                });
            }
        }
    }, [props.show]);
    return (
        <Modal
            size="md"
            aria-labelledby="contained-modal-title-vcenter"
            centered
            show={props.show}
            onHide={props.onHide}
        >
            <Modal.Header
                closeButton
            >
                <Modal.Title className="Header">Leaderboard</Modal.Title>
            </Modal.Header>

            <Modal.Body>
                <div className="Entries">
                    <p id="Title">Top WPMs</p>
                    {leaderboard.map(([name, wpm], index) => (
                        <LeaderboardEntry
                            name={name}
                            index={index}
                            rank={index + 1}
                            score={wpm}
                        />
                    ))}
                </div>
            </Modal.Body>
        </Modal>
    );
}
