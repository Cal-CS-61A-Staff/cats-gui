import React from "react";
import "./Indicators.css";

export default function Indicators(props) {
    return (
        <div className="Indicators">
            <Indicator text={`WPM: ${props.wpm}`} />
            <Indicator text={`Accuracy: ${props.accuracy}`} />
            <Indicator text={`Time: ${props.remainingTime}`} />
        </div>
    );
}

function Indicator(props) {
    return (
        <div className="Indicator">
            {props.text}
        </div>
    );
}
