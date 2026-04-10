pipeline {
    agent any

    environment {
        APP_NAME = 'pdf-manager'
        IMAGE_NAME = "farhanniqom/${APP_NAME}"
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
                echo "Running lint..."
                sh 'docker build --target lint -t pdf-manager-lint .'
            }
        }

        stage('Docker Build') {
            steps {
                echo "Building Docker image..."
                sh "docker build -t ${IMAGE_NAME}:${IMAGE_TAG} -t ${IMAGE_NAME}:latest ."
            }
        }

        stage('Cleanup') {
            steps {
                sh "docker image prune -f"
            }
        }

        stage('Deploy') {
            when {
                branch 'main'
            }
            steps {
                echo "Deploying with Docker Compose..."
                sh "docker compose down --remove-orphans"
                sh "docker compose up -d --build"
                sh "docker run -d --name ${APP_NAME} -p 9000:9000 ${IMAGE_NAME}:${IMAGE_TAG}"
            }
        }
    }

    post {
        always {
            cleanWs()
        }
    }
}