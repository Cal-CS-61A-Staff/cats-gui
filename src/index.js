import React from "react";
import ReactDOM from "react-dom";
import "./index.css";
import App from "./App";
import * as serviceWorker from "./serviceWorker";

document.body.prepend(new Comment(String.raw`
 _________________________________________ 
/ Hello adventurous student! If you want  \
| to see the source of the GUI, go to Dev |
| Tools => Sources => Page => top =>      |
| [this domain] => static => js and       |
\ enjoy!                                  /
 ----------------------------------------- 
  \
   \
    \                         _
     \                       | \
      \                      | |
                             | |
        |\                   | |
       /, ~\                / /
      X     \`-.....-------./ /
       ~-. ~  ~              |
          \             /    |
           \  /_     ___\   /
           | /\ ~~~~~   \ |
           | | \        || |
           | |\ \       || )
          (_/ (_/      ((_/
`));

ReactDOM.render(<App />, document.getElementById("root"));

// If you want your app to work offline and load faster, you can change
// unregister() to register() below. Note this comes with some pitfalls.
// Learn more about service workers: https://bit.ly/CRA-PWA
serviceWorker.unregister();
