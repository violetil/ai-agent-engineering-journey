# My AI service.

1. Install depends

   ```bash
   pip install -r requirements.txt
   ```

2. Enter project folder

   ```bash
   cd week3_python_abilities/ai_service
   ```

3. Launch the AI API service

   ```bash
   uvicorn app.main:app --reload --port 8000
   ```

4. Check the API docs in `http://127.0.0.1/docs`
