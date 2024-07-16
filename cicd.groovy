node('linux')
{
  stage ('Poll') {
    checkout([
      $class: 'GitSCM',
      branches: [[name: '*/main']],
      doGenerateSubmoduleConfigurations: false,
      extensions: [],
      userRemoteConfigs: [[url: 'https://github.com/ZOSOpenTools/c3270port.git']]])
  }
  stage('Build') {
    build job: 'Port-Pipeline', parameters: [
      string(name: 'PORT_GITHUB_REPO', value: 'https://github.com/ZOSOpenTools/c3270port.git'), 
      string(name: 'PORT_DESCRIPTION', value: '3270 terminal' ), 
      string(name: 'NODE_LABEL', value: "v3r1"
    ]
  }
}
