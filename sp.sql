CREATE OR ALTER PROCEDURE dbo.usp_ProcessInstruments
AS
BEGIN
    SET NOCOUNT ON;
    SET XACT_ABORT ON;

    --------------------------------------------------------------------
    -- Cursor over the latest version per instrument in STAGING
    --------------------------------------------------------------------
    DECLARE @instrumentId       BIGINT,
            @instrument_status  VARCHAR(50),
            @name               VARCHAR(200),
            @version            INT,
            @errMsg             NVARCHAR(4000),
            @existingVersion    INT;

    ;WITH LatestStaging AS
    (
        SELECT instrumentId, instrument_status, name, version
        FROM
        (
            SELECT si.*,
                   ROW_NUMBER() OVER (PARTITION BY si.instrumentId ORDER BY si.version DESC) AS rn
            FROM dbo.staging_instrument si
        ) x
        WHERE x.rn = 1
    )
    DECLARE cur CURSOR LOCAL FAST_FORWARD FOR
        SELECT instrumentId, instrument_status, name, version
        FROM LatestStaging;

    OPEN cur;
    FETCH NEXT FROM cur INTO @instrumentId, @instrument_status, @name, @version;

    WHILE @@FETCH_STATUS = 0
    BEGIN
        BEGIN TRY
            ----------------------------------------------------------------
            -- Start per-instrument transaction
            ----------------------------------------------------------------
            BEGIN TRAN;

            -- Lock the main row (if present) to avoid races while we compare versions
            SET @existingVersion = NULL;
            SELECT @existingVersion = i.version
            FROM dbo.instrument AS i WITH (UPDLOCK, HOLDLOCK)
            WHERE i.instrumentId = @instrumentId;

            ----------------------------------------------------------------
            -- Process only if staging.version > main.version (strictly greater)
            ----------------------------------------------------------------
            IF (@existingVersion IS NOT NULL AND @version <= @existingVersion)
            BEGIN
                -- Nothing to do for this instrument; log and move on
                ROLLBACK TRAN;

                SET @errMsg = CONCAT(
                    'Skipped: staging version ', @version,
                    ' <= main version ', COALESCE(CAST(@existingVersion AS NVARCHAR(20)),'NULL')
                );

                INSERT INTO dbo.[error] (instrumentId, error_desc)
                VALUES (@instrumentId, @errMsg);

                -- Next instrument
                FETCH NEXT FROM cur INTO @instrumentId, @instrument_status, @name, @version;
                CONTINUE;
            END

            ----------------------------------------------------------------
            -- Validate country_code mapping for all staging instrument_id rows
            -- If any mapping is missing, skip the entire instrument
            ----------------------------------------------------------------
            IF EXISTS
            (
                SELECT 1
                FROM dbo.staging_instrument_id s
                LEFT JOIN dbo.country_code c
                    ON c.country = s.country_code
                WHERE s.instrumentId = @instrumentId
                  AND c.country_id IS NULL
            )
            BEGIN
                ROLLBACK TRAN;

                INSERT INTO dbo.[error] (instrumentId, error_desc)
                VALUES (@instrumentId, 'Missing country_code mapping in country_code table');

                FETCH NEXT FROM cur INTO @instrumentId, @instrument_status, @name, @version;
                CONTINUE;
            END

            ----------------------------------------------------------------
            -- Upsert parent row (instrument)
            ----------------------------------------------------------------
            IF (@existingVersion IS NULL)
            BEGIN
                INSERT INTO dbo.instrument (instrumentId, instrument_status, name, version)
                VALUES (@instrumentId, @instrument_status, @name, @version);
            END
            ELSE
            BEGIN
                UPDATE dbo.instrument
                SET instrument_status = @instrument_status,
                    name             = @name,
                    version          = @version
                WHERE instrumentId  = @instrumentId;
            END

            ----------------------------------------------------------------
            -- Replace child rows: instrument_desc
            ----------------------------------------------------------------
            DELETE FROM dbo.instrument_desc
            WHERE instrumentId = @instrumentId;

            INSERT INTO dbo.instrument_desc (instrumentId, [desc])
            SELECT d.instrumentId, d.[desc]
            FROM dbo.staging_instrument_desc d
            WHERE d.instrumentId = @instrumentId;

            ----------------------------------------------------------------
            -- Replace child rows: instrument_id (mapped to country_id)
            ----------------------------------------------------------------
            DELETE FROM dbo.instrument_id
            WHERE instrumentId = @instrumentId;

            INSERT INTO dbo.instrument_id (instrumentId, instrument_id_type, country_id)
            SELECT s.instrumentId, s.instrument_id_type, c.country_id
            FROM dbo.staging_instrument_id s
            INNER JOIN dbo.country_code c
                ON c.country = s.country_code
            WHERE s.instrumentId = @instrumentId;

            ----------------------------------------------------------------
            -- Commit per-instrument
            ----------------------------------------------------------------
            COMMIT TRAN;
        END TRY
        BEGIN CATCH
            -- Roll back this instrument and log the error; continue with next
            IF XACT_STATE() <> 0
                ROLLBACK TRAN;

            SET @errMsg = CONCAT(
                'Error ', ERROR_NUMBER(),
                ' at line ', ERROR_LINE(), ': ',
                ERROR_MESSAGE()
            );

            INSERT INTO dbo.[error] (instrumentId, error_desc)
            VALUES (@instrumentId, @errMsg);
        END CATCH;

        FETCH NEXT FROM cur INTO @instrumentId, @instrument_status, @name, @version;
    END

    CLOSE cur;
    DEALLOCATE cur;
END
GO
