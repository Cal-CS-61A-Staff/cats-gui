import React, { useRef } from "react";
import Modal from "react-bootstrap/Modal";

export default function NamePrompt(props) {
    const inputRef = useRef(null);

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
                <Modal.Title className="Header">High Score</Modal.Title>
            </Modal.Header>

            <Modal.Body>
                Congratulations! Your WPM is fast enough to place on our leaderboard! Enter a name here to associate it with your score:
                <br />
                <form onSubmit={(e) => { e.preventDefault(); props.onSubmit(inputRef.current.value); }}>
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
                    {
                        props.captchaRequired ?
                        <div className="form-group">
                            <i>Because of your high WPM, you will be required to complete a short CAPTCHA before you will be allowed to submit. <br />
                            Don't worry about getting every word correct. You are allowed fairly large margin of error for mistakes.</i>
                        </div> :
                        ""
                    }
                    <div className="form-group">
                        {
                            !props.captchaRequired ?
                            <button type="submit" className="btn btn-primary">Submit</button> :
                            <button className="btn btn-warning">Captcha</button>
                        }
                        {" "}
                        <button type="button" onClick={props.onHide} className="btn btn-danger">I cheated, please don't include my score</button>
                    </div>
                </form>
            </Modal.Body>
        </Modal>
    );
}
