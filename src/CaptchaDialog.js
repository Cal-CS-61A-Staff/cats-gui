import React from "react";
import Modal from "react-bootstrap/Modal";
import Button from "react-bootstrap/Button";
import CaptchaImage from "./CaptchaImage.js";
import "./CaptchaDialog.css";

export default function CaptchaDialog(props) {
    const captchaRef = React.createRef();

    return (
        <Modal
            size="lg"
            aria-labelledby="contained-modal-title-vcenter"
            centered
            show={props.show}
        >
            <Modal.Header>
                <Modal.Title>CAPTCHA</Modal.Title>
            </Modal.Header>

            <Modal.Body className="CaptchaDialog">
                <CaptchaImage captchaUris={props.captchaUris} />
                <textarea ref={captchaRef}></textarea>
            </Modal.Body>
            
            <Modal.Footer>
                {
                    !props.submitted ?
                    <Button onClick={() => props.handleSubmitCaptcha(captchaRef.current.value)}>Submit</Button> :
                    <Button disabled="true" variant={props.passed ? "success" : "danger"}>{props.passed ? "Passed" : "Failed"}</Button>
                }
            </Modal.Footer>
        </Modal>
    );
}
