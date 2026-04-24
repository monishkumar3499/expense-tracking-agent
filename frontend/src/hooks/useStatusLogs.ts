import { useState, useEffect } from 'react';

export function useStatusLogs() {
    const [lastLog, setLastLog] = useState<string>('');
    const [isActive, setIsActive] = useState(false);

    useEffect(() => {
        const baseUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
        console.log(`📡 [S-LOG] Connecting to ${baseUrl}/api/status/stream...`);
        const eventSource = new EventSource(`${baseUrl}/api/status/stream`);
        let timer: NodeJS.Timeout;

        eventSource.onmessage = (event) => {
            console.log("📡 [S-LOG] Received:", event.data);
            setLastLog(event.data);
            setIsActive(true);
            
            if (timer) clearTimeout(timer);
            timer = setTimeout(() => {
                setIsActive(false);
            }, 5000);
        };

        eventSource.onerror = () => {
            setIsActive(false);
        };

        return () => {
            if (timer) clearTimeout(timer);
            eventSource.close();
        };
    }, []);

    return { lastLog, isActive };
}
