web tile grid
 - app tile cell:
  - header:
   - health icons section (one icon side by side w/ env name for each env where): 
    * green - healthy/ok 
    * yellow - deploying/transitioning to a new version per pipeline blue/green deploy to aws ecs fargate cluster - main use case per app model config input on app startup 
    * red - unhealthy/unresponsive/failed state
   
  key data points to convey:
   - num current user http sessions per env (prod at minimum of coure)
   - cloudwatch log tails (per env) along with core aggregate stats:
    - num cumulative errors since last boot
    - ?
   - http incoming request agtregate stats (from ALB aws api inferred from knowing deployment pipeline name and greping the audit for deployment history)
   - count and detail msg of blocked requests and source http info
   - aggtregate counts/stats since <date - by month w/ link to history of prior months or line to aws consule  .. (icon) .. 
     (TODO: refine key ingress aggregate stats missing ui elements/.)
   - deployment history / git source most recent 3 probablyu .. icons dude clean ui bare naked ad no more but links to dreill down deeper for each aspect of what isconveyed as agrouping categoryiezing elemtns and theme of hierarchy .. likened to bitch we can go as dep as you want keep[ clickng and alyws knowng the ui is celan and unambiguouse 
    - and each elemetn within is coupled with version and deployment event responsible .. 
  
   

- Header
 - UC img logo
 - org/group section:
  - org and group name - "dashboard" header text
  - links below for:
   - confluence
   - service now
   - datadog
   - group lelel link to box 
 - members
 - project sources (link to codecommit)
 - TODO add missing essentials

 - Breadcrumbs (horiz row below header):
  - current app path links to easily nav out (back)

 - Alerts Banner row (shows aws cli based alerts at present)

 - Main body (container div type boundary)
  - app grid with tile for each managed app in group
  - the tile show core essential info/status

- Footer
 - UC copyright boilerplate
 - dashboard version, deploymenbt timestamp.

 