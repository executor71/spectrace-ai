package com.example.legacyassistant.jobs;
import javax.sql.DataSource;
import java.sql.Connection;
import org.springframework.stereotype.Component;
import com.example.legacyassistant.analysis.AnalysisException;

/** A dedicated session lock survives transaction boundaries; every sync/job caller shares it. */
@Component
public class AnalysisGate {
    public static final long KEY=140001;
    private final DataSource source;
    public AnalysisGate(DataSource source){this.source=source;}
    public Lease tryAcquire(){
        Connection connection=null;
        try{connection=source.getConnection();try(var q=connection.prepareStatement("SELECT pg_try_advisory_lock(?)")){
            q.setLong(1,KEY);try(var rows=q.executeQuery()){rows.next();if(rows.getBoolean(1))return new Lease(connection);}
        }connection.close();return null;}catch(Exception e){if(connection!=null)try{connection.close();}catch(Exception ignored){}throw new AnalysisException(503,"JOB_WORKER_ERROR","분석 실행 자원을 확인할 수 없습니다.");}
    }
    public static final class Lease implements AutoCloseable {
        private final Connection connection;
        Lease(Connection connection){this.connection=connection;}
        public boolean valid(){try{return connection.isValid(2);}catch(Exception e){return false;}}
        @Override public void close(){try{try(var q=connection.prepareStatement("SELECT pg_advisory_unlock(?)")){q.setLong(1,KEY);q.execute();}}catch(Exception ignored){}finally{try{connection.close();}catch(Exception ignored){}}}
    }
}
