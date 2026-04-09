pipeline {
    agent any

    environment {
        APP_NAME = 'pdf-manager'
        IMAGE_NAME = "farhanniqom/${APP_NAME}" // Change this to your registry/username
        IMAGE_TAG = "${env.BUILD_NUMBER}"
    }

    stages {
        stage('Checkout') {
            steps {
                checkout scm
            }
        }

        stage('Code Linting') {
            steps {
                sh "pip install flake8 --user"
                sh "python3 -m flake8 app/ --exclude=__pycache__,venv --max-line-length=120"
            }
        }

        stage('Docker Build') {
            steps {
                echo "Building Docker Image: ${IMAGE_NAME}:${IMAGE_TAG}"
                sh "docker build -t ${IMAGE_NAME}:${IMAGE_TAG} -t ${IMAGE_NAME}:latest -f DockerFile ."
            }
        }

        stage('Push to Registry') {
            when {
                branch 'main'
            }
            steps {
                // UNCOMMENT and configure 'docker-hub-credentials' in Jenkins to enable pushing
                // withCredentials([usernamePassword(credentialsId: 'docker-hub-credentials', usernameVariable: 'USER', passwordVariable: 'PASS')]) {
                //     sh "docker login -u ${USER} -p ${PASS}"
                //     sh "docker push ${IMAGE_NAME}:${IMAGE_TAG}"
                //     sh "docker push ${IMAGE_NAME}:latest"
                // }
                echo "Push stage skipped. Configure credentials and registry in Jenkinsfile to enable."
            }
        }

        stage('Deploy') {
            when {
                branch 'main'
            }
            steps {
                echo "Deploying application using Docker Compose..."
                sh "docker compose down --remove-orphans"
                sh "docker compose up -d"
            }
        }
    }

    post {
        always {
            echo "Cleaning up workspace..."
            cleanWs()
        }
        success {
            echo "Pipeline completed successfully!"
        }
        failure {
            echo "Pipeline failed. Check build logs."
        }
    }
}
