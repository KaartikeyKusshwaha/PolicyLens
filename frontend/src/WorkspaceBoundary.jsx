import { Component } from "react";

export default class WorkspaceBoundary extends Component {
  state = { failed: false };
  static getDerivedStateFromError() { return { failed: true }; }
  render() {
    if (this.state.failed) return <section className="panel section-padding" role="alert"><h2>The workspace could not finish loading.</h2><p>Check your connection, then reload to download the latest application.</p><button className="button primary" onClick={() => window.location.reload()}>Reload workspace</button></section>;
    return this.props.children;
  }
}
