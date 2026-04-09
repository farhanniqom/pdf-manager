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
                sh 'docker build --target lint -t pdf-manager-lint .'
            }
        }

        stage('Docker Build') {
            steps {
                sh "docker build -t ${IMAGE_NAME}:${IMAGE_TAG} -t ${IMAGE_NAME}:latest ."
            }
        }

        stage('Push to Registry') {
            when {
                branch 'main'
            }
            steps {
                echo "Push skipped (belum setup credentials)"
            }
        }

        stage('Deploy') {
            when {
                branch 'main'
            }
            steps {
                echo "Deploy skipped (belum setup remote server)"
            }
        }
    }

    post {
        always {
            cleanWs()
        }
    }
}