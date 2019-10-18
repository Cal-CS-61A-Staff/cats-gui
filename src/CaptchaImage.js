import React from "react";
import "./CaptchaImage.css"

export default function CaptchaImage(props) {
    let images = props.captchaUris.map((uri) => {
        return <img
            src={uri}
            alt="Captcha"
        />;
    });
    return (
        <div className="CaptchaImage">
            {images}
        </div>
    );
}
