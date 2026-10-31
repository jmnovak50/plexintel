export const FOUNDATION_CONTENT = {
  engagement:{title:'Community Engagement',question:'Who is predicted to engage with the retained titles?',sections:[
    ['Prediction history','Future model-versioned snapshots will retain each applicable user’s engagement prediction, ranking and explanation for each retained title.'],
    ['Offer qualification','A future binary decision will determine whether a title warrants an offer. No predictions or offer decisions exist in this workspace yet.'],
    ['Assignment evidence','Prediction snapshots will inform a separate assignment decision. Ranking changes and supersession history will remain inspectable. No expiration or holding period is imposed.']]},
  requests:{title:'Request Management',question:'Who should be notified, and what happened to the offer?',sections:[
    ['Assignments and supersession','Future requester decisions will preserve the selected user, prediction evidence and preceding assignment. Reassignment is driven by new evidence.'],
    ['Notifications and responses','Notification intent, delivery and explicit release/decline actions will be separate events. Ignored notifications are neutral.'],
    ['External requests','Future reconciliation will observe requests made directly through Seerr/Plexgen with source identity and reliably known requester. No notification or request automation is implemented.']]},
  queue:{title:'My Request Queue',question:'What titles has PlexIntel offered me, and what do I want to do?',sections:[
    ['Current offers','Assigned offers will appear here when request management is implemented. This foundation does not query or create assignments.'],
    ['Your decisions','Future explicit release through Plexgen and decline actions will capture request intent separately from playback engagement. No actionable requests are available.'],
    ['Prior offers','Future history will show your responses and superseded offers. An unanswered offer is neutral and has no arbitrary expiry.']]},
} as const;
