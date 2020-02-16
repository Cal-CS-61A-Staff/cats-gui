import { useEffect, useRef } from "react";

export const getCurrTime = () => (new Date()).getTime() / 1000;

export const formatNum = (num) => (num ? num.toFixed(1) : "None");


export function useInterval(callback, delay) {
    const savedCallback = useRef();

    useEffect(() => {
        savedCallback.current = callback;
    }, [callback]);

    // eslint-disable-next-line consistent-return
    useEffect(() => {
        function tick() {
            savedCallback.current();
        }
        if (delay !== null) {
            const id = setInterval(tick, delay);
            return () => clearInterval(id);
        }
    }, [delay]);
}
