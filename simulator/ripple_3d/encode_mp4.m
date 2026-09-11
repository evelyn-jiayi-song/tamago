#import <AVFoundation/AVFoundation.h>
#import <CoreVideo/CoreVideo.h>
#import <Foundation/Foundation.h>

static void fail(NSString *message, int code) {
    fprintf(stderr, "%s\n", message.UTF8String);
    exit(code);
}

int main(int argc, const char *argv[]) {
    @autoreleasepool {
        if (argc != 7) {
            fail(@"usage: encode_mp4 <rgb-frames> <output.mp4> <width> <height> <fps> <frame-count>", 2);
        }
        NSString *rawPath = [NSString stringWithUTF8String:argv[1]];
        NSString *outputPath = [NSString stringWithUTF8String:argv[2]];
        int width = atoi(argv[3]);
        int height = atoi(argv[4]);
        int fps = atoi(argv[5]);
        int frameCount = atoi(argv[6]);
        NSUInteger frameBytes = (NSUInteger)width * (NSUInteger)height * 3;

        NSFileManager *files = [NSFileManager defaultManager];
        [files removeItemAtPath:outputPath error:nil];
        NSURL *outputURL = [NSURL fileURLWithPath:outputPath];
        NSError *error = nil;
        AVAssetWriter *writer = [[AVAssetWriter alloc] initWithURL:outputURL
                                                            fileType:AVFileTypeMPEG4
                                                               error:&error];
        if (!writer) fail(error.localizedDescription ?: @"could not create video writer", 3);

        NSDictionary *compression = @{
            AVVideoAverageBitRateKey: @5500000,
            AVVideoExpectedSourceFrameRateKey: @(fps),
            AVVideoMaxKeyFrameIntervalKey: @(fps),
        };
        NSDictionary *settings = @{
            AVVideoCodecKey: AVVideoCodecTypeH264,
            AVVideoWidthKey: @(width),
            AVVideoHeightKey: @(height),
            AVVideoCompressionPropertiesKey: compression,
        };
        AVAssetWriterInput *input = [AVAssetWriterInput assetWriterInputWithMediaType:AVMediaTypeVideo
                                                                          outputSettings:settings];
        input.expectsMediaDataInRealTime = NO;
        NSDictionary *attributes = @{
            (id)kCVPixelBufferPixelFormatTypeKey: @(kCVPixelFormatType_32BGRA),
            (id)kCVPixelBufferWidthKey: @(width),
            (id)kCVPixelBufferHeightKey: @(height),
            (id)kCVPixelBufferCGBitmapContextCompatibilityKey: @YES,
            (id)kCVPixelBufferCGImageCompatibilityKey: @YES,
            (id)kCVPixelBufferIOSurfacePropertiesKey: @{},
        };
        [writer addInput:input];
        if (![writer startWriting]) fail(writer.error.localizedDescription ?: @"could not start video writer", 4);
        [writer startSessionAtSourceTime:kCMTimeZero];

        NSData *raw = [NSData dataWithContentsOfFile:rawPath options:0 error:&error];
        if (!raw) fail(error.localizedDescription ?: @"could not read raw frames", 5);
        if (raw.length != frameBytes * (NSUInteger)frameCount) fail(@"unexpected raw frame data size", 6);
        const uint8_t *source = raw.bytes;

        for (int index = 0; index < frameCount; index++) {
            while (!input.readyForMoreMediaData) [NSThread sleepForTimeInterval:0.001];
            CVPixelBufferRef buffer = NULL;
            CVReturn status = CVPixelBufferCreate(kCFAllocatorDefault, width, height,
                                                   kCVPixelFormatType_32BGRA, (__bridge CFDictionaryRef)attributes, &buffer);
            if (status != kCVReturnSuccess || !buffer) fail(@"could not create pixel buffer", 7);
            CVPixelBufferLockBaseAddress(buffer, 0);
            uint8_t *destination = CVPixelBufferGetBaseAddress(buffer);
            size_t destinationStride = CVPixelBufferGetBytesPerRow(buffer);
            const uint8_t *frame = source + (NSUInteger)index * frameBytes;
            for (int y = 0; y < height; y++) {
                const uint8_t *sourceRow = frame + (NSUInteger)y * (NSUInteger)width * 3;
                uint8_t *destinationRow = destination + (NSUInteger)y * destinationStride;
                for (int x = 0; x < width; x++) {
                    int si = x * 3;
                    int di = x * 4;
                    destinationRow[di] = sourceRow[si + 2];
                    destinationRow[di + 1] = sourceRow[si + 1];
                    destinationRow[di + 2] = sourceRow[si];
                    destinationRow[di + 3] = 255;
                }
            }
            CVPixelBufferUnlockBaseAddress(buffer, 0);
            CMVideoFormatDescriptionRef format = NULL;
            CMVideoFormatDescriptionCreateForImageBuffer(kCFAllocatorDefault, buffer, &format);
            CMSampleTimingInfo timing = {
                CMTimeMake(1, fps),
                CMTimeMake(index, fps),
                CMTimeMake(index, fps),
            };
            CMSampleBufferRef sample = NULL;
            OSStatus sampleStatus = CMSampleBufferCreateReadyWithImageBuffer(
                kCFAllocatorDefault, buffer, format, &timing, &sample);
            if (format) CFRelease(format);
            if (sampleStatus != noErr || !sample) {
                if (sample) CFRelease(sample);
                CVPixelBufferRelease(buffer);
                fail([NSString stringWithFormat:@"could not create sample buffer (status %d)", (int)sampleStatus], 8);
            }
            if (![input appendSampleBuffer:sample]) {
                NSString *detail = writer.error.localizedDescription ?: @"unknown error";
                CFRelease(sample);
                CVPixelBufferRelease(buffer);
                fail([NSString stringWithFormat:@"could not append video frame %d: %@", index, detail], 8);
            }
            CFRelease(sample);
            CVPixelBufferRelease(buffer);
        }

        [input markAsFinished];
        dispatch_semaphore_t done = dispatch_semaphore_create(0);
        [writer finishWritingWithCompletionHandler:^{ dispatch_semaphore_signal(done); }];
        dispatch_semaphore_wait(done, DISPATCH_TIME_FOREVER);
        if (writer.status != AVAssetWriterStatusCompleted) {
            NSError *writerError = writer.error;
            NSString *detail = writerError
                ? [NSString stringWithFormat:@"%@ (domain=%@ code=%ld)", writerError.localizedDescription,
                   writerError.domain, (long)writerError.code]
                : @"video writer failed without an NSError";
            fail(detail, 9);
        }
    }
    return 0;
}
