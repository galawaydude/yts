import React from 'react';

const ReadmeModal = ({ onClose }) => {
  return (
    <div className="modal-backdrop">
      <div className="modal-content">
        <h2 className="modal-title">Some Stuff</h2>
        
        <div className="modal-body">
          <p>Hello</p>
          <p>
            Thank you for showing interest in using my application, but there are some issues you should know before hand.
            Do not want to dissapoint you, I have worked a lot on the backend of this application to make it as scalabale as possible. 
            Have used redis and celery workers to enable parallel processing of the video indexing. But the major bottle neck with my application, is an issue, i cannot fix.
          </p>
          
          <h3 className="modal-subtitle">The Bottleneck: Youtube</h3>
          <p>
            I am using the very popular Youtube-Transcript-API to get transcript for indexing, and its a pretty good package.
            How it works is by scrapping Youtube to get the information. The issue here is that, because this application is deployed on GCP, Youtube has an IP ban on request from these IPs.
            And to fix this issue, I used Webshare's Rotating Residential Proxies.
          </p>
          
          <h3 className="modal-subtitle">What This Means For You</h3>
          <p>
            <span className="text-highlight-red">
              This is actually a pretty good way of getting around the IP ban, but the issue is, there is only so much I can spend on this application, and the bandwidth I paid for has exhausted.
              The transcript fetching surprisingly takes up a lot of bandwidth, because of the way the YouTube-Transcript-API works.
            </span>
          </p>
          <p>
            <span className="text-highlight-red">
              So, because of this, A lot of the proxies fail, and the whole process becames very slow, I am working on fixing this issue.
            </span>
          </p>
        </div>

        <button className="modal-close-button" onClick={onClose}>
          Exit
        </button>
      </div>
    </div>
  );
};

export default ReadmeModal;