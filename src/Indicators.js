import React from "react";
import "./Indicators.css";

const formatNum = (num) => (num ? num.toFixed(1) : "None");

export default function Indicators({ wpm, accuracy, remainingTime }) {
    return (
        <div className="Indicators">
            <Indicator text={`WPM: ${formatNum(wpm)}`} />
            <Indicator text={`Accuracy: ${formatNum(accuracy)}`} />
            <Indicator text={`Time: ${remainingTime}`} />
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
