import React, { Component } from "react";
import "./App.css";
import "bootstrap/dist/css/bootstrap.min.css";
import "bootstrap/dist/js/bootstrap.min.js";
import $ from "jquery";
import Button from "react-bootstrap/Button.js";
import CaptchaDialog from "./CaptchaDialog.js";
import Input from "./Input.js";
import Indicators from "./Indicators.js";
import Leaderboard from "./Leaderboard.js";
import LoadingDialog from "./LoadingDialog.js";
import Options from "./Options.js";
import OpeningDialog from "./OpeningDialog.js";
import Prompt from "./Prompt.js";
import ProgressBars from "./ProgressBars.js";
import NamePrompt from "./NamePrompt.js";

export const Mode = {
    SINGLE: "single",
    MULTI: "multi",
    WELCOME: "welcome",
    WAITING: "waiting",
};

class App extends Component {
    constructor(props) {
        super(props);
        this.state = {
            promptedWords: ["Please wait - loading!"],
            typedWords: [],
            wpm: "None",
            accuracy: "None",
            startTime: 0,
            currTime: 0,
            pigLatin: false,
            autoCorrect: false,
            currWord: "",
            inputActive: false,
            numPlayers: 1,
            mode: Mode.SINGLE,
            playerList: [],
            progress: [],
            showLeaderboard: false,
            fastestWords: "",
            showUsernameEntry: false,
            memes: false,
            pToken: "",
            sToken: "",
            wpmToken: "",
            username: "",
            captchaRequired: false,
            captchaUris: [],
            captchaToken: "",
            showCaptcha: false,
        };
        this.timer = null;
        this.multiplayerTimer = null;

        $.post("/request_id").done((id) => {
            if (id !== null) {
                this.setState({ id: id.toString(), mode: Mode.WELCOME });
            }
        });
    }

    componentDidMount() {
        this.initialize();
    }

    componentDidUpdate() {
        if (this.state.mode === Mode.WELCOME
            || this.state.mode === Mode.WAITING
            || this.state.showLeaderboard
        ) {
            document.getElementById("app-root").style.filter = "blur(5px)";
        } else {
            document.getElementById("app-root").style.filter = "none";
        }
    }

    componentWillUnmount() {
        clearInterval(this.timer);
        clearInterval(this.multiplayerTimer);
    }

    initialize = () => {
        this.setState({
            typedWords: [],
            currWord: "",
            inputActive: true,
            wpm: "None",
            accuracy: "None",
        });

        $.post("/request_paragraph").done((data) => {
            this.setState({
                pToken: data.pToken,
                sToken: "",
                wpmToken: "",
            });
            if (this.state.pigLatin) {
                $.post("/translate_to_pig_latin", {
                    text: data.paragraph,
                }, (translated) => {
                    this.setState({
                        promptedWords: translated.split(" "),
                    });
                });
            } else {
                this.setState({
                    promptedWords: data.paragraph.split(" "),
                });
            }
        });

        this.setState({ startTime: 0, currTime: 0 });

        clearInterval(this.timer);
        this.timer = null;
    };

    restart = () => {
        this.timer = setInterval(this.updateReadouts, 100);
        this.setState({
            startTime: this.getCurrTime(),
            currTime: this.getCurrTime(),
        });
    };

    updateReadouts = () => {
        const promptedText = this.state.promptedWords.join(" ");
        const typedText = this.state.typedWords.join(" ");
        $.post("/analyze", {
            promptedText,
            typedText,
            startTime: this.state.startTime,
            endTime: this.getCurrTime(),
            pToken: this.state.pToken,
            sToken: this.state.sToken,
        }).done((data) => {
            this.setState({
                wpm: data.wpm.toFixed(1),
                accuracy: data.accuracy.toFixed(1),
                currTime: this.getCurrTime(),
            });
            if (data.hasOwnProperty("sToken")) {
                this.setState({
                    pToken: "",
                    sToken: data.sToken
                });
            } else if (data.hasOwnProperty("wpmToken")) {
                this.setState({
                    sToken: "",
                    wpmToken: data.wpmToken,
                });
                if (data.hasOwnProperty("captchaRequired")) {
                    this.setState({
                        captchaRequired: data.captchaRequired,
                    });
                }
            }
        });
    };

    reportProgress = () => {
        const promptedText = this.state.promptedWords.join(" ");
        $.post("/report_progress", {
            id: this.state.id,
            typed: this.state.typedWords.join(" "),
            prompt: promptedText,
        });
    };

    requestProgress = () => {
        $.post("/request_progress", {
            targets: this.state.playerList,
        }).done((progress) => {
            this.setState({
                progress,
            });
            if (progress.every((p) => p[0] === 1.0)) {
                clearInterval(this.multiplayerTimer);
                this.fastestWords();
            }
        });
    };

    fastestWords = () => {
        $.post("/fastest_words", {
            targets: this.state.playerList,
            prompt: this.state.promptedWords.join(" "),
        }).done((fastestWords) => {
            this.setState({ fastestWords });
        });
    };

    popPrevWord = () => {
        if (this.state.typedWords.length !== 0) {
            const out = this.state.typedWords[this.state.typedWords.length - 1];
            this.setState((state) => ({
                typedWords: state.typedWords.slice(0, state.typedWords.length - 1),
            }));
            return out;
        } else {
            return "";
        }
    };

    getCurrTime = () => (new Date()).getTime() / 1000;

    handleWordTyped = (word) => {
        if (!word) {
            return true;
        }

        const wordIndex = this.state.typedWords.length;

        const afterWordTyped = () => {
            this.updateReadouts();
            if (this.state.mode === Mode.MULTI) {
                this.reportProgress();
            }
        };

        this.setState((state) => {
            if (state.autoCorrect && word !== state.promptedWords[wordIndex]) {
                $.post("/autocorrect", { word }).done((data) => {
                    // eslint-disable-next-line no-shadow
                    this.setState((state) => {
                        if (state.typedWords[wordIndex] !== word) {
                            return {};
                        }
                        const { typedWords } = state;
                        typedWords[wordIndex] = data;
                        return { typedWords };
                    });
                });
            }

            return {
                typedWords: state.typedWords.concat([word]),
                currWord: "",
            };
        }, afterWordTyped);

        return true;
    };

    handleChange = (currWord) => {
        this.setState({ currWord });
        if (this.state.typedWords.length + 1 === this.state.promptedWords.length
            && this.state.promptedWords[this.state.promptedWords.length - 1] === currWord) {
            clearInterval(this.timer);
            this.setState({ inputActive: false });
            this.handleWordTyped(currWord);
            $.post("/wpm_threshold", (threshold) => {
                if (this.state.wpm >= threshold && parseFloat(this.state.accuracy) === 100) {
                    this.setState({ showUsernameEntry: true });
                }
            });
        } else if (!this.timer) {
            this.restart();
        }
    };

    handlePigLatinToggle = () => {
        this.initialize();
        this.setState((state) => ({
            autoCorrect: false,
            pigLatin: !state.pigLatin,
        }));
    };

    handleAutoCorrectToggle = () => {
        this.initialize();
        this.setState((state) => ({
            autoCorrect: !state.autoCorrect,
            pigLatin: false,
        }));
    };

    setMode = (mode) => {
        this.setState({ mode });
        if (mode === Mode.WAITING) {
            this.multiplayerTimer = setInterval(this.requestMatch, 1000);
        }
    };

    requestMatch = () => {
        $.post("/request_match", { id: this.state.id }).done((data) => {
            if (data.start) {
                this.setState({
                    mode: Mode.MULTI,
                    playerList: data.players,
                    numPlayers: data.players.length,
                    promptedWords: data.text.split(" "),
                    progress: new Array(data.players.length).fill([0, 0]),
                    pigLatin: false,
                    autoCorrect: false,
                    pToken: data.pToken,
                });
                clearInterval(this.multiplayerTimer);
                this.multiplayerTimer = setInterval(this.requestProgress, 500);
            } else {
                this.setState({
                    numPlayers: data.numWaiting,
                });
            }
        });
    };

    toggleLeaderBoard = (memes) => {
        this.setState(({ showLeaderboard }) => ({
            showLeaderboard: !showLeaderboard,
            memes,
        }));
    };

    handleUsernameSubmission = (username) => {
        this.setState({
            username: username,
        }, () => {
            if (this.state.captchaRequired) {
                this.requestCaptcha();
            } else {
                this.submitUsername();
            }
        });
        this.hideUsernameEntry();
    };

    submitUsername = () => {
        $.post("/record_wpm", {
            username: this.state.username,
            wpm: this.state.wpm,
            wpmToken: this.state.wpmToken,
        });
        this.setState({
            username: "",
            wpmToken: "",
        });
    }

    hideUsernameEntry = () => {
        this.setState({ showUsernameEntry: false });
    };

    requestCaptcha = () => {
        $.get("/get_captcha").done((data) => {
            this.setState({
                captchaUris: data.captchaUris,
                captchaToken: data.captchaToken,
                showCaptcha: true,
            });
        });
    }

    handleSubmitCaptcha = (typed) => {
        // TODO Implement
    }

    render() {
        const {
            wpm, accuracy, numPlayers, startTime, currTime, playerList, id, fastestWords,
        } = this.state;
        const remainingTime = (currTime - startTime).toFixed(1);
        const playerIndex = playerList.indexOf(id);
        const fastestWordsDisplay = (
            <div>
                <pre>{fastestWords}</pre>
            </div>
        );

        return (
            <>
                <div className="App container" id="app-root">
                    <div className="row">
                        <div className="col">
                            <br />
                            <div className="LeaderboardButton">
                                <Button onClick={() => this.toggleLeaderBoard(false)} variant="outline-dark">Leaderboard</Button>
                                <Button onClick={() => this.toggleLeaderBoard(true)} variant="outline-dark">Memeboard</Button>
                            </div>
                            <h1 className="display-4 mainTitle">
                                {/* eslint-disable-next-line react/jsx-one-expression-per-line */}
                                <b>C</b>S61A <b>A</b>utocorrected <b>T</b>yping <b>S</b>oftware
                            </h1>
                            <br />
                            <Indicators
                                wpm={wpm}
                                accuracy={accuracy}
                                remainingTime={remainingTime}
                            />
                            {this.state.mode === Mode.MULTI
                            && (
                                <ProgressBars
                                    numPlayers={numPlayers}
                                    progress={this.state.progress}
                                    playerIndex={playerIndex}
                                />
                            )}
                            <br />
                            <Prompt
                                promptedWords={this.state.promptedWords}
                                typedWords={this.state.typedWords}
                                currWord={this.state.currWord}
                            />
                            <br />
                            <Input
                                key={this.state.promptedWords[0]}
                                correctWords={this.state.promptedWords}
                                words={this.state.typedWords}
                                onWordTyped={this.handleWordTyped}
                                onChange={this.handleChange}
                                popPrevWord={this.popPrevWord}
                                active={this.state.inputActive}
                            />
                            <br />
                            {this.state.mode !== Mode.MULTI
                            && (
                                <Options
                                    pigLatin={this.state.pigLatin}
                                    onPigLatinToggle={this.handlePigLatinToggle}
                                    autoCorrect={this.state.autoCorrect}
                                    onAutoCorrectToggle={this.handleAutoCorrectToggle}
                                    onRestart={this.initialize}
                                />
                            )}
                            {this.state.mode === Mode.MULTI && fastestWordsDisplay}
                        </div>
                    </div>
                </div>
                <OpeningDialog
                    show={this.state.mode === Mode.WELCOME}
                    setMode={this.setMode}
                    toggleFindingOpponents={this.toggleFindingOpponents}
                />
                <LoadingDialog
                    show={this.state.mode === Mode.WAITING}
                    numPlayers={this.state.numPlayers}
                />
                <Leaderboard
                    show={this.state.showLeaderboard}
                    memes={this.state.memes}
                    onHide={this.toggleLeaderBoard}
                />
                <NamePrompt
                    show={this.state.showUsernameEntry}
                    onHide={this.hideUsernameEntry}
                    onSubmit={this.handleUsernameSubmission}
                    captchaRequired={this.state.captchaRequired}
                />
                <CaptchaDialog
                    show={this.state.showCaptcha}
                    captchaUris={this.state.captchaUris}
                    handleSubmitCaptcha={this.handleSubmitCaptcha}
                />
            </>
        );
    }
}

export default App;
