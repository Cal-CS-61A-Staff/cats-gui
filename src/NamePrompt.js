import React, { useRef } from "react";
import Modal from "react-bootstrap/Modal";

export default function NamePrompt({ show, onHide, onSubmit }) {
    const inputRef = useRef(null);

    return (
        <Modal
            size="md"
            aria-labelledby="contained-modal-title-vcenter"
            centered
            show={show}
            onHide={onHide}
        >
            <Modal.Header
                closeButton
            >
                <Modal.Title className="Header">High Score</Modal.Title>
            </Modal.Header>

            <Modal.Body>
                Congratulations! Your WPM is fast enough to place on our leaderboard! Enter a name here to associate it with your score:
                <br />
                <form onSubmit={(e) => { e.preventDefault(); onSubmit(inputRef.current.value); }}>
                    <div className="form-group">
                        <input
                            type="text"
                            ref={inputRef}
                            className="form-control"
                            id="exampleInputEmail1"
                            aria-describedby="emailHelp"
                            placeholder="Enter username"
                            maxlength="32"
                        />
                        <small id="emailHelp" className="form-text text-muted">
                    Please don't name yourself anything inappropriate!
                        </small>
                    </div>
                    <div className="form-group">
                        <button type="submit" className="btn btn-primary">Submit</button>
                        {" "}
                        <button type="button" onClick={onHide} className="btn btn-danger">I cheated, please don't include my score</button>
                    </div>
                </form>
            </Modal.Body>
        </Modal>
    );
}
