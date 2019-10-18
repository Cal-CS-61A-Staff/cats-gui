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

            <Modal.Body>
                <CaptchaImage captchaUris={props.captchaUris} />
                <input ref={captchaRef}/>
            </Modal.Body>
            
            <Modal.Footer>
                <Button onClick={() => props.handleSubmitCaptcha(captchaRef.current.value)}>Submit</Button>
            </Modal.Footer>
        </Modal>
    );
}
